# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, date
from odoo.exceptions import ValidationError

class BadmintonAttendanceCheck(models.Model):
    _name = 'badminton.attendance.check.genclik'
    _description = 'Badminton Dərs İştirakı Yoxlaması'
    _order = 'check_date desc'
    
    name = fields.Char(string="Yoxlama Adı", readonly=True, default="Yeni")
    coach_id = fields.Many2one('res.partner', string="Məşqçi", required=True, domain=[('is_coach', '=', True)])
    group_id = fields.Many2one('badminton.group.genclik', string="Qrup", required=True)
    
    # Yoxlama təfərrüatları
    check_date = fields.Date(string="Yoxlama Tarixi", required=True, default=fields.Date.today)
    schedule_id = fields.Many2one('badminton.group.schedule.genclik', string="Dərs Vaxtı", required=True,
                                  domain="[('group_id', '=', group_id)]")
    day_of_week = fields.Selection(related='schedule_id.day_of_week', string="Həftənin Günü", store=True, readonly=True)
    
    # İştirakçılar
    attendee_ids = fields.One2many('badminton.attendance.check.line.genclik', 'attendance_check_id', string="İştirakçılar")
    attendee_count = fields.Integer(string="İştirakçı Sayı", compute='_compute_attendee_count')
    present_count = fields.Integer(string="İştirak Edənlərin Sayı", compute='_compute_present_count')
    
    # Vəziyyət
    state = fields.Selection([
        ('draft', 'Layihə'),
        ('confirmed', 'Təsdiqlənib'),
        ('cancelled', 'Ləğv Edilib')
    ], default='draft', string="Vəziyyət")
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")

    @api.model
    def create(self, vals):
        if vals.get('name', 'Yeni') == 'Yeni':
            vals['name'] = self.env['ir.sequence'].next_by_code('badminton.attendance.check.genclik') or 'BAC001'
        return super(BadmintonAttendanceCheck, self).create(vals)
    
    @api.depends('attendee_ids')
    def _compute_attendee_count(self):
        for check in self:
            check.attendee_count = len(check.attendee_ids)
    
    @api.depends('attendee_ids.is_present')
    def _compute_present_count(self):
        for check in self:
            check.present_count = len(check.attendee_ids.filtered(lambda a: a.is_present))
    
    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup seçildikdə avtomatik iştirakçıları əlavə et"""
        self.schedule_id = False
        self.attendee_ids = [(5, 0, 0)]  # Əvvəlki iştirakçıları təmizlə
    
    @api.onchange('schedule_id')
    def _onchange_schedule_id(self):
        """Dərs qrafiki seçildikdə qrup üzvlərini əlavə et"""
        if self.group_id and self.schedule_id:
            # Clear previous attendees
            self.attendee_ids = [(5, 0, 0)]
            
            # Qrupun aktiv üzvlərini əldə et
            members = self.env['badminton.lesson.simple.genclik'].search([
                ('group_id', '=', self.group_id.id),
                ('state', 'in', ['active', 'frozen'])
            ])
            
            if not members:
                return
                
            # İştirakçı sətirləri yarad
            attendee_vals = []
            for member in members:
                # Make sure the lesson exists
                if member and member.id:
                    attendee_vals.append((0, 0, {
                        'partner_id': member.partner_id.id,
                        'lesson_id': member.id,
                        'is_present': False
                    }))
            
            if attendee_vals:
                self.attendee_ids = attendee_vals
    
    def action_confirm(self):
        """İştirak yoxlamasını təsdiqlə və iştirakları qeydə al"""
        for check in self:
            if check.state == 'draft':
                # İştirakları qeydə al
                for attendee in check.attendee_ids:
                    if attendee.is_present:
                        # Uyğun dərs qrafikini tap
                        schedule = attendee.lesson_id.schedule_ids.filtered(
                            lambda s: s.day_of_week == check.schedule_id.day_of_week
                        )
                        
                        if schedule:
                            # İştiraklara əlavə et
                            self.env['badminton.lesson.attendance.simple.genclik'].create({
                                'lesson_id': attendee.lesson_id.id,
                                'schedule_id': schedule[0].id,
                                'attendance_date': check.check_date,
                                'attendance_time': datetime.now(),
                                'qr_scanned': False,
                                'notes': f"Yoxlama ilə əlavə edilib: {check.name}"
                            })
                
                check.state = 'confirmed'
    
    def action_cancel(self):
        """İştirak yoxlamasını ləğv et"""
        for check in self:
            check.state = 'cancelled'
    
    def action_draft(self):
        """İştirak yoxlamasını layihə vəziyyətinə qaytar"""
        for check in self:
            check.state = 'draft'


class BadmintonAttendanceCheckLine(models.Model):
    _name = 'badminton.attendance.check.line.genclik'
    _description = 'Badminton Dərs İştirakı Yoxlaması Sətri'
    
    attendance_check_id = fields.Many2one('badminton.attendance.check.genclik', string="İştirak Yoxlaması", 
                                         required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string="İştirakçı", required=True)
    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Abunəlik", required=True,
                               domain="[('partner_id', '=', partner_id), ('state', 'in', ['active', 'frozen'])]")
    
    # İştirak statusu
    is_present = fields.Boolean(string="İştirak edir", default=False)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Partner seçildikdə uyğun dərsləri yüklə"""
        if self.partner_id:
            # Find active lessons for this partner in the same group
            domain = [
                ('partner_id', '=', self.partner_id.id),
                ('state', 'in', ['active', 'frozen'])
            ]
            
            if self.attendance_check_id.group_id:
                domain.append(('group_id', '=', self.attendance_check_id.group_id.id))

            lessons = self.env['badminton.lesson.simple.genclik'].search(domain)

            if lessons:
                self.lesson_id = lessons[0].id
            else:
                self.lesson_id = False
    
    _sql_constraints = [
        ('unique_partner_attendance', 'unique(attendance_check_id, partner_id)', 
         'Hər müştəri bir yoxlamada yalnız bir dəfə ola bilər!')
    ]
    
    @api.constrains('partner_id', 'lesson_id')
    def _check_lesson_partner(self):
        """İştirakçı və dərsin uyğun olub olmadığını yoxlayır"""
        for record in self:
            if record.partner_id and record.lesson_id and record.lesson_id.partner_id != record.partner_id:
                raise ValidationError(f"Seçilmiş dərs {record.partner_id.name} üçün deyil. Xahiş edirik doğru dərsi seçin.")
