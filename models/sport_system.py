# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date

class SportBranch(models.Model):
    _name = 'sport.branch.genclik'
    _description = 'İdman Növü'
    
    name = fields.Char(string="İdman Növü", required=True)
    code = fields.Char(string="Kod", required=True)
    description = fields.Text(string="Təsvir")
    is_hourly = fields.Boolean(string="Saatlıq Xidmət", default=False, help="Badminton kimi saatlıq xidmət")
    is_monthly = fields.Boolean(string="Aylıq Dərs", default=False)

class SportSchedule(models.Model):
    _name = 'sport.schedule.genclik'
    _description = 'İdman Qrafiki'
    
    name = fields.Char(string="Qrafik Adı", compute='_compute_name', store=True)
    branch_id = fields.Many2one('sport.branch.genclik', string="İdman Növü", required=True)

    # Vaxt məlumatları
    day_of_week = fields.Selection([
        ('0', 'Bazar ertəsi'),
        ('1', 'Çərşənbə axşamı'),
        ('2', 'Çərşənbə'),
        ('3', 'Cümə axşamı'),
        ('4', 'Cümə'),
        ('5', 'Şənbə'),
        ('6', 'Bazar')
    ], string="Həftənin Günü", required=True)
    
    start_time = fields.Float(string="Başlama Saatı", required=True, help="Məsələn 19.5 = 19:30")
    end_time = fields.Float(string="Bitmə Saatı", required=True, help="Məsələn 21.0 = 21:00")
    
    # Dərs məlumatları
    instructor_id = fields.Many2one('res.partner', string="Müəllim")
    max_students = fields.Integer(string="Maksimum Tələbə Sayı", default=12)
    is_active = fields.Boolean(string="Aktiv", default=True)

    @api.depends('branch_id', 'day_of_week', 'start_time')
    def _compute_name(self):
        days = {
            '0': 'B.ertəsi', '1': 'Ç.axşamı', '2': 'Çərşənbə', 
            '3': 'C.axşamı', '4': 'Cümə', '5': 'Şənbə', '6': 'Bazar'
        }
        for schedule in self:
            if schedule.branch_id and schedule.day_of_week:
                day_name = days.get(schedule.day_of_week, '')
                hour = int(schedule.start_time)
                minute = int((schedule.start_time - hour) * 60)
                time_str = f"{hour:02d}:{minute:02d}"
                schedule.name = f"{schedule.branch_id.name} - {day_name} {time_str}"
            else:
                schedule.name = "Yeni Qrafik"


class SportMembership(models.Model):
    _name = 'sport.membership.genclik'
    _description = 'İdman Üzvlüyü'
    
    name = fields.Char(string="Üzvlük Nömrəsi", readonly=True, default="Yeni")
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    branch_id = fields.Many2one('sport.branch.genclik', string="İdman Növü", required=True)
    schedule_ids = fields.Many2many('sport.schedule.genclik', string="Qrafiklər")
    
    # Aylıq dərs sistemi üçün
    month = fields.Integer(string="Ay", required=True)
    year = fields.Integer(string="İl", required=True)
    total_lessons = fields.Integer(string="Ümumi Dərs Sayı", compute='_compute_total_lessons', store=True)
    attended_lessons = fields.Integer(string="İştirak Etdiyi Dərslər", default=0)
    remaining_lessons = fields.Integer(string="Qalan Dərslər", compute='_compute_remaining_lessons')
    
    # Ödəniş və vəziyyət
    monthly_fee = fields.Float(string="Aylıq Ödəniş", compute='_compute_monthly_fee', store=True)
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    state = fields.Selection([
        ('draft', 'Gözləmədə'),
        ('active', 'Aktiv'),
        ('expired', 'Vaxtı Keçib'),
        ('cancelled', 'Ləğv Edilib')
    ], default='draft', string="Vəziyyət")
    
    @api.depends('year', 'month', 'schedule_ids')
    def _compute_total_lessons(self):
        for membership in self:
            if membership.year and membership.month and membership.schedule_ids:
                # Ayın tam həftələrinin sayını hesabla
                first_day = date(membership.year, membership.month, 1)
                if membership.month == 12:
                    last_day = date(membership.year + 1, 1, 1) - timedelta(days=1)
                else:
                    last_day = date(membership.year, membership.month + 1, 1) - timedelta(days=1)
                
                total_weeks = 0
                current_date = first_day
                
                while current_date <= last_day:
                    week_start = current_date - timedelta(days=current_date.weekday())
                    week_end = week_start + timedelta(days=6)
                    
                    # Həftə tam ayın içindədirsə
                    if week_start >= first_day and week_end <= last_day:
                        total_weeks += 1
                    
                    current_date += timedelta(days=7)
                
                # Hər qrafik üçün həftələrin sayı qədər dərs
                membership.total_lessons = total_weeks * len(membership.schedule_ids)
            else:
                membership.total_lessons = 0
    
    @api.depends('total_lessons', 'attended_lessons')
    def _compute_remaining_lessons(self):
        for membership in self:
            membership.remaining_lessons = membership.total_lessons - membership.attended_lessons

    @api.depends('branch_id')
    def _compute_monthly_fee(self):
        for membership in self:
            membership.monthly_fee = 0.0
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'Yeni') == 'Yeni':
            vals['name'] = self.env['ir.sequence'].next_by_code('sport.membership.genclik') or 'SM001'
        return super(SportMembership, self).create(vals)


class SportAttendance(models.Model):
    _name = 'sport.attendance.genclik'
    _description = 'Dərsə İştirak'
    
    membership_id = fields.Many2one('sport.membership.genclik', string="Üzvlük", required=True)
    schedule_id = fields.Many2one('sport.schedule.genclik', string="Qrafik", required=True)
    attendance_date = fields.Date(string="İştirak Tarixi", default=fields.Date.today)
    attendance_time = fields.Datetime(string="İştirak Vaxtı", default=fields.Datetime.now)
    
    # QR scan məlumatları
    qr_scanned = fields.Boolean(string="QR Oxunub", default=False)
    scan_result = fields.Text(string="Scan Nəticəsi")
    
    # Vəziyyət
    is_valid = fields.Boolean(string="Etibarlı", compute='_compute_is_valid', store=True)
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('membership_id', 'schedule_id', 'attendance_date')
    def _compute_is_valid(self):
        for attendance in self:
            if attendance.membership_id and attendance.schedule_id and attendance.attendance_date:
                # Üzvlüyün aktiv olub olmadığını yoxla
                membership = attendance.membership_id
                schedule = attendance.schedule_id
                
                # Tarix yoxlaması
                attendance_date = attendance.attendance_date
                year_month_valid = (attendance_date.year == membership.year and 
                                  attendance_date.month == membership.month)
                
                # Həftənin günü yoxlaması
                day_of_week_valid = str(attendance_date.weekday()) == schedule.day_of_week
                
                # Qrafik aktiv olub olmadığını yoxla
                schedule_active = schedule.is_active
                
                # Üzvlük aktiv olub olmadığını yoxla
                membership_active = membership.is_active and membership.state == 'active'
                
                attendance.is_valid = (year_month_valid and day_of_week_valid and 
                                     schedule_active and membership_active)
            else:
                attendance.is_valid = False
