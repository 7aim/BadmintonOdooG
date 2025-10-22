# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class BadmintonLessonSimple(models.Model):
    _name = 'badminton.lesson.simple.genclik'
    _description = 'Badminton Dərsi (Sadə)'
    _order = 'create_date desc'
    
    name = fields.Char(string="Dərs Nömrəsi", readonly=True, default="Yeni")
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    group_id = fields.Many2one('badminton.group.genclik', string="Qrup")
    
    # Paket seçimi - yalnız abunəlik paketləri
    package_id = fields.Many2one('badminton.package.genclik', string="Abunəlik Paketi",
                                  domain="[('package_type', '=', 'subscription'), ('active', '=', True)]")
    
    # Dərs Qrafiki (həftənin günləri)
    schedule_ids = fields.One2many('badminton.lesson.schedule.simple.genclik', 'lesson_id', string="Həftəlik Qrafik")
    
    # İştiraklar
    attendance_ids = fields.One2many('badminton.lesson.attendance.simple.genclik', 'lesson_id', string="Dərsə İştiraklar")
    total_attendances = fields.Integer(string="Ümumi İştirak", compute='_compute_total_attendances')
    
    # Ödəniş məlumatları
    lesson_fee = fields.Float(string="Aylıq Dərs Haqqı", default=100.0, store=True)
    original_price = fields.Float(string="Endirimsiz Qiymət", readonly=True)

    # Tarix məlumatları
    start_date = fields.Date(string="Cari Dövr Başlama", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Cari Dövr Bitmə", compute='_compute_end_date', store=True, readonly=False)
    
    # Abunəlik məlumatları
    total_months = fields.Integer(string="Ümumi Abunəlik (ay)", default=1)
    total_payments = fields.Float(string="Ümumi Ödəniş", compute='_compute_total_payments')
    
    # Dondurma məlumatları
    freeze_ids = fields.One2many('badminton.lesson.freeze.genclik', 'lesson_id', string="Dondurma Tarixçəsi")
    total_freeze_days = fields.Integer(string="Ümumi Donma Günləri", compute='_compute_total_freeze_days', store=True)
    current_freeze_id = fields.Many2one('badminton.lesson.freeze.genclik', string="Cari Dondurma", compute='_compute_current_freeze', store=True)

    # Vəziyyət
    state = fields.Selection([
        ('draft', 'Layihə'),
        ('active', 'Aktiv'),
        ('frozen', 'Dondurulmuş'),
        ('completed', 'Tamamlanıb'),
        ('cancelled', 'Ləğv Edilib')
    ], default='draft', string="Vəziyyət")
    
    # Ödəniş tarixi
    payment_date = fields.Datetime(string="Ödəniş Tarixi")
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('start_date')
    def _compute_end_date(self):
        for lesson in self:
            if lesson.start_date:
                # 1 ay əlavə et
                lesson.end_date = lesson.start_date + timedelta(days=30)
            else:
                lesson.end_date = False
    

    
    @api.depends('total_months', 'lesson_fee')
    def _compute_total_payments(self):
        for lesson in self:
            lesson.total_payments = lesson.total_months * lesson.lesson_fee
    
    @api.depends('attendance_ids')
    def _compute_total_attendances(self):
        for lesson in self:
            lesson.total_attendances = len(lesson.attendance_ids)
            
    @api.depends('freeze_ids.freeze_days', 'freeze_ids.state')
    def _compute_total_freeze_days(self):
        for lesson in self:
            total_days = 0
            for freeze in lesson.freeze_ids.filtered(lambda f: f.state in ['active', 'completed']):
                total_days += freeze.freeze_days
            lesson.total_freeze_days = total_days
            
    @api.depends('freeze_ids.state', 'freeze_ids.freeze_start_date', 'freeze_ids.freeze_end_date')
    def _compute_current_freeze(self):
        today = fields.Date.today()
        for lesson in self:
            current_freeze = lesson.freeze_ids.filtered(lambda f: 
                f.state == 'active' and 
                f.freeze_start_date <= today and 
                f.freeze_end_date >= today
            )
            lesson.current_freeze_id = current_freeze[0].id if current_freeze else False
    
    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup seçildikdə avtomatik qrafik əlavə et"""
        if self.group_id:
            # Əvvəlki qrafiki sil
            self.schedule_ids = [(5, 0, 0)]
            
            # Qrupun qrafikini kopyala
            schedule_vals = []
            for group_schedule in self.group_id.schedule_ids:
                if group_schedule.is_active:
                    schedule_vals.append((0, 0, {
                        'day_of_week': group_schedule.day_of_week,
                        'start_time': group_schedule.start_time,
                        'end_time': group_schedule.end_time,
                        'is_active': True,
                        'notes': f"Qrup qrafiki: {self.group_id.name}"
                    }))
            
            if schedule_vals:
                self.schedule_ids = schedule_vals
    
    @api.onchange('package_id')
    def _onchange_package_id(self):
        """Paket seçildikdə avtomatik qiyməti təyin et"""
        if self.package_id:
            # Endirimsiz qiymət
            original_price = self.package_id.adult_price
            self.original_price = original_price
            
            # Endirim hesabla
            if self.package_id.discount_percent > 0:
                discount_amount = original_price * (self.package_id.discount_percent / 100)
                self.lesson_fee = original_price - discount_amount
            else:
                self.lesson_fee = original_price
        else:
            self.original_price = 0.0
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'Yeni') == 'Yeni':
            vals['name'] = self.env['ir.sequence'].next_by_code('badminton.lesson.simple.genclik') or 'BLS001'
            
        return super(BadmintonLessonSimple, self).create(vals)
    
    def action_confirm(self):
        """Dərsi təsdiqlə və ödənişi qəbul et"""
        for lesson in self:
            if lesson.state == 'draft':
                lesson.state = 'active'
                lesson.payment_date = fields.Datetime.now()
                
                # Kassaya əməliyyatı əlavə et
                self.env['volan.cash.flow.genclik'].create({
                    'name': f"Badminton dərs abunəliyi: {lesson.name}",
                    'date': fields.Date.today(),
                    'amount': lesson.lesson_fee,
                    'transaction_type': 'income',
                    'category': 'badminton_lesson',
                    'partner_id': lesson.partner_id.id,
                    'related_model': 'badminton.lesson.simple.genclik',
                    'related_id': lesson.id,
                    'notes': f"Abunəlik dövrü: {lesson.start_date} - {lesson.end_date}"
                })
    
    def action_renew(self):
        """Abunəliyi 1 ay uzat və yenidən ödəniş qəbul et"""
        for lesson in self:
            if lesson.state == 'active':
                # Başlama tarixi sabit qalır, yalnız end_date uzanır
                old_end_date = lesson.end_date
                lesson.end_date = lesson.end_date + timedelta(days=30)
                lesson.total_months += 1
                lesson.payment_date = fields.Datetime.now()
                
                # Yeni sequence nömrəsi ver (isteğe bağlı)
                lesson.name = f"{lesson.name.split('-')[0]}-R{lesson.total_months}"
                
                # Kassaya əməliyyatı əlavə et
                self.env['volan.cash.flow.genclik'].create({
                    'name': f"Badminton dərs yeniləməsi: {lesson.name}",
                    'date': fields.Date.today(),
                    'amount': lesson.lesson_fee,
                    'transaction_type': 'income',
                    'category': 'badminton_lesson',
                    'partner_id': lesson.partner_id.id,
                    'related_model': 'badminton.lesson.simple.genclik',
                    'related_id': lesson.id,
                    'notes': f"Abunəlik yeniləməsi: {old_end_date} - {lesson.end_date}"
                })
    
    def action_complete(self):
        """Dərsi tamamla"""
        for lesson in self:
            if lesson.state == 'active':
                lesson.state = 'completed'
    
    def action_freeze(self):
        """Abunəliyi dondur - Wizard aç"""
        for lesson in self:
            if lesson.state == 'active':
                return {
                    'name': 'Abunəliyi Dondur',
                    'type': 'ir.actions.act_window',
                    'res_model': 'badminton.lesson.freeze.wizard.genclik',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_lesson_id': lesson.id,
                        'default_partner_id': lesson.partner_id.id,
                        'default_freeze_start_date': fields.Date.today(),
                        'default_freeze_end_date': fields.Date.today() + timedelta(days=7),  # Default 1 week
                    }
                }
    
    def action_unfreeze(self):
        """Abunəliyi aktiv et"""
        for lesson in self:
            if lesson.state == 'frozen' and lesson.current_freeze_id:
                # Cari dondurmanı tamamlandı kimi işarələ
                lesson.current_freeze_id.action_complete()
                # Yeni end_date hesabla - donma günləri qədər uzat
                if lesson.end_date:
                    freeze_days = lesson.current_freeze_id.freeze_days
                    lesson.end_date = lesson.end_date + timedelta(days=freeze_days)
                # Abunəliyi aktiv et
                lesson.state = 'active'
    
    def action_cancel(self):
        """Dərsi ləğv et"""
        for lesson in self:
            if lesson.state in ['draft', 'active', 'frozen']:
                lesson.state = 'cancelled'


class BadmintonLessonScheduleSimple(models.Model):
    _name = 'badminton.lesson.schedule.simple.genclik'
    _description = 'Həftəlik Dərs Qrafiki (Sadə)'
    _order = 'day_of_week, start_time'
    
    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Dərs", required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='lesson_id.partner_id', string="Müştəri", store=True)
    
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
    
    def name_get(self):
        """Dərs vaxtını daha anlaşıqlı formada göstər"""
        result = []
        day_names = dict(self._fields['day_of_week'].selection)
        for schedule in self:
            start_hours = int(schedule.start_time)
            start_minutes = int((schedule.start_time - start_hours) * 60)
            end_hours = int(schedule.end_time)
            end_minutes = int((schedule.end_time - end_hours) * 60)
            
            formatted_time = f"{day_names[schedule.day_of_week]} {start_hours:02d}:{start_minutes:02d}-{end_hours:02d}:{end_minutes:02d}"
            result.append((schedule.id, formatted_time))
        return result
    
    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for schedule in self:
            if schedule.start_time >= schedule.end_time:
                raise ValidationError("Başlama vaxtı bitmə vaxtından kiçik olmalıdır!")
            if schedule.start_time < 0 or schedule.start_time > 24:
                raise ValidationError("Başlama vaxtı 0-24 aralığında olmalıdır!")
            if schedule.end_time < 0 or schedule.end_time > 24:
                raise ValidationError("Bitmə vaxtı 0-24 aralığında olmalıdır!")

class BadmintonLessonAttendanceSimple(models.Model):
    _name = 'badminton.lesson.attendance.simple.genclik'
    _description = 'Badminton Dərs İştirakı (Sadə)'
    _order = 'attendance_date desc, attendance_time desc'

    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Dərs Abunəliyi", required=True)
    schedule_id = fields.Many2one('badminton.lesson.schedule.simple.genclik', string="Dərs Qrafiki", required=True)
    partner_id = fields.Many2one(related='lesson_id.partner_id', string="Müştəri", store=True)
    
    # İştirak məlumatları
    attendance_date = fields.Date(string="İştirak Tarixi", default=fields.Date.today)
    attendance_time = fields.Datetime(string="İştirak Vaxtı", default=fields.Datetime.now)
    
    # QR scan məlumatları  
    qr_scanned = fields.Boolean(string="QR ilə Giriş", default=True)
    scan_result = fields.Text(string="QR Nəticəsi")
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")