# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BadmintonGroup(models.Model):
    _name = 'badminton.group.genclik'
    _description = 'Badminton Qrupu'
    _order = 'name'
    
    name = fields.Char(string="Qrup Adı", required=True)
    description = fields.Text(string="Təsvir")
    
    # Qrup qrafiki
    schedule_ids = fields.One2many('badminton.group.schedule.genclik', 'group_id', string="Qrup Qrafiki")
    
    # Qrup üzvləri
    member_ids = fields.One2many('badminton.lesson.simple.genclik', 'group_id', string="Qrup Üzvləri")
    member_count = fields.Integer(string="Üzv Sayı", compute='_compute_member_count')
    
    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('member_ids')
    def _compute_member_count(self):
        for group in self:
            group.member_count = len(group.member_ids.filtered(lambda l: l.state in ['active', 'frozen']))


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