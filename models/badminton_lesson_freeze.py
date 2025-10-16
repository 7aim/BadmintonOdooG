# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class BadmintonLessonFreeze(models.Model):
    _name = 'badminton.lesson.freeze.genclik'
    _description = 'Badminton Abunəlik Dondurması'
    _order = 'freeze_start_date desc'
    
    name = fields.Char(string="Dondurma Kodu", readonly=True, default="/")
    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Abunəlik", required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string="Müştəri", related="lesson_id.partner_id", store=True, readonly=True)
    
    # Dondurma tarixi məlumatları
    freeze_start_date = fields.Date(string="Dondurma Başlanğıcı", required=True, default=fields.Date.today)
    freeze_end_date = fields.Date(string="Dondurma Sonu", required=True)
    freeze_days = fields.Integer(string="Donma Günləri", compute="_compute_freeze_days", store=True)
    
    # Vəziyyət
    state = fields.Selection([
        ('active', 'Aktiv'),
        ('completed', 'Tamamlanmış'),
        ('cancelled', 'Ləğv Edilib')
    ], default='active', string="Vəziyyət")
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('freeze_start_date', 'freeze_end_date')
    def _compute_freeze_days(self):
        for record in self:
            if record.freeze_start_date and record.freeze_end_date:
                if record.freeze_end_date >= record.freeze_start_date:
                    delta = record.freeze_end_date - record.freeze_start_date
                    record.freeze_days = delta.days + 1  # Include both start and end day
                else:
                    record.freeze_days = 0
            else:
                record.freeze_days = 0
                
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('badminton.lesson.freeze.genclik') or 'FRZ/001'
            
        return super(BadmintonLessonFreeze, self).create(vals)
    
    def action_complete(self):
        """Dondurma bitdi"""
        for freeze in self:
            freeze.state = 'completed'
            
    def action_cancel(self):
        """Dondurma ləğv et"""
        for freeze in self:
            freeze.state = 'cancelled'
