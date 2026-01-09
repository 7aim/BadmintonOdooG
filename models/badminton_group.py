# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BadmintonGroup(models.Model):
    _name = 'badminton.group.genclik'
    _description = 'Badminton Qrupu'
    _order = 'sequence, name DESC'
    
    sequence = fields.Integer(string="Sıra", default=10)
    name = fields.Char(string="Qrup Adı", required=True)
    description = fields.Text(string="Təsvir")
    
    # Qrup qrafiki
    schedule_ids = fields.One2many('badminton.group.schedule.genclik', 'group_id', string="Qrup Qrafiki")
    
    # Qrup üzvləri
    member_ids = fields.Many2many('badminton.lesson.simple.genclik', 'badminton_lesson_group_rel', 'group_id', 'lesson_id', string="Qrup Üzvləri", compute='_compute_member_ids')
    member_count = fields.Integer(string="Üzv Sayı", compute='_compute_member_count')
    unique_new_members_count = fields.Integer(string="Yeni Unikal Üzv", compute='_compute_unique_new_members', store=False)

    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    def _compute_member_ids(self):
        """Bu qrupa aid olan aktiv abunəlikləri tap"""
        for group in self:
            lessons = self.env['badminton.lesson.simple.genclik'].search([
                ('group_ids', 'in', group.id),
                ('state', '!=', 'cancelled')
            ])
            group.member_ids = [(6, 0, lessons.ids)]
    
    @api.depends('member_ids', 'member_ids.state', 'member_ids.partner_id')
    def _compute_member_count(self):
        for group in self:
            active_members = group.member_ids.filtered(lambda l: l.state in ['active', 'frozen'])
            unique_partners = active_members.mapped('partner_id')
            group.member_count = len(unique_partners)
    
    def _compute_unique_new_members(self):
        """Hər qrupda yalnız yeni (əvvəlki qruplarda olmayan) müştəriləri say"""
        all_groups = self.search([('is_active', '=', True)], order='sequence, name DESC')
        seen_partners = set()
        
        for group in all_groups:
            if group.id in self.ids:
                active_members = group.member_ids.filtered(lambda l: l.state in ['active', 'frozen'])
                group_partners = set(active_members.mapped('partner_id').ids)
                
                # Bu qrupda yeni olan müştəriləri tap
                new_partners = group_partners - seen_partners
                group.unique_new_members_count = len(new_partners)
                
                # Bu qrupun bütün müştərilərini seen_partners-ə əlavə et
                seen_partners.update(group_partners)
            else:
                active_members = group.member_ids.filtered(lambda l: l.state in ['active', 'frozen'])
                seen_partners.update(active_members.mapped('partner_id').ids)
    
    @api.model
    def create(self, vals):
        return super(BadmintonGroup, self).create(vals)


class BadmintonGroupSchedule(models.Model):
    _name = 'badminton.group.schedule.genclik'
    _description = 'Badminton Qrup Qrafiki'
    _order = 'day_of_week, start_time'

    group_id = fields.Many2one('badminton.group.genclik', string="Qrup", required=True, ondelete='cascade')
    
    # Həftənin günü
    day_of_week = fields.Selection([
        ('0', 'Bazar ertəsi'),
        ('1', 'Çərşənbə axşamı'),
        ('2', 'Çərşənbə'),
        ('3', 'Cümə axşamı'),
        ('4', 'Cümə'),
        ('5', 'Şənbə'),
        ('6', 'Bazar')
    ], string="Həftənin Günü", required=True)
    
    # Vaxt aralığı
    start_time = fields.Float(string="Başlama Vaxtı", required=True, help="Məsələn 19.5 = 19:30")
    end_time = fields.Float(string="Bitmə Vaxtı", required=True, help="Məsələn 20.5 = 20:30")
    
    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for schedule in self:
            if schedule.start_time >= schedule.end_time:
                raise ValidationError("Başlama vaxtı bitmə vaxtından kiçik olmalıdır!")
            if schedule.start_time < 0 or schedule.start_time > 24:
                raise ValidationError("Başlama vaxtı 0-24 aralığında olmalıdır!")
            if schedule.end_time < 0 or schedule.end_time > 24:
                raise ValidationError("Bitmə vaxtı 0-24 aralığında olmalıdır!")
    
    @api.model
    def create(self, vals):
        """Qrup qrafiki yaradılanda bütün üzvlərin qrafikini yenilə"""
        schedule = super(BadmintonGroupSchedule, self).create(vals)
        schedule._sync_member_schedules()
        return schedule
    
    def write(self, vals):
        """Qrup qrafiki dəyişəndə bütün üzvlərin qrafikini yenilə"""
        result = super(BadmintonGroupSchedule, self).write(vals)
        self._sync_member_schedules()
        return result
    
    def unlink(self):
        """Qrup qrafiki silinəndə üzvlərdən də sil"""
        for schedule in self:
            schedule._sync_member_schedules(delete=True)
        return super(BadmintonGroupSchedule, self).unlink()
    
    def _sync_member_schedules(self, delete=False):
        """Qrup üzvlərinin qrafikini sinxronlaşdır"""
        self.ensure_one()
        
        # Bu qrupun bütün aktiv üzvlərini tap (Many2many əlaqə)
        members = self.env['badminton.lesson.simple.genclik'].search([
            ('group_ids', 'in', self.group_id.id),
            ('state', 'in', ['active', 'frozen'])
        ])
        
        for member in members:
            if delete:
                # Qrup qrafiki silinir - üzvdən də sil
                member_schedule = member.schedule_ids.filtered(
                    lambda s: s.day_of_week == self.day_of_week and 
                             s.start_time == self.start_time and
                             s.end_time == self.end_time
                )
                if member_schedule:
                    member_schedule.unlink()
            else:
                # Qrup qrafiki yaradılır və ya dəyişir - üzvdə yenilə
                # Əvvəlcə eyni günə aid köhnə qrafiki tap
                existing_schedule = member.schedule_ids.filtered(
                    lambda s: s.day_of_week == self.day_of_week
                )
                
                if existing_schedule:
                    # Mövcud qrafiki yenilə
                    existing_schedule.write({
                        'start_time': self.start_time,
                        'end_time': self.end_time,
                        'is_active': self.is_active,
                        'notes': f"Qrup qrafiki: {self.group_id.name} (avtomatik yeniləndi)"
                    })
                else:
                    # Yeni qrafik yarat
                    self.env['badminton.lesson.schedule.simple.genclik'].create({
                        'lesson_id': member.id,
                        'day_of_week': self.day_of_week,
                        'start_time': self.start_time,
                        'end_time': self.end_time,
                        'is_active': self.is_active,
                        'notes': f"Qrup qrafiki: {self.group_id.name} (avtomatik əlavə edildi)"
                    })
