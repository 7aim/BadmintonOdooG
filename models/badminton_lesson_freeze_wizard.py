# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class BadmintonLessonFreezeWizard(models.TransientModel):
    _name = 'badminton.lesson.freeze.wizard.genclik'
    _description = 'Abunəlik Dondurma Sehrbazı'

    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Abunəlik", required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string="Müştəri", related="lesson_id.partner_id", readonly=True)
    
    # Dondurma tarixi məlumatları
    freeze_start_date = fields.Date(string="Dondurma Başlanğıcı", required=True, default=fields.Date.today)
    freeze_end_date = fields.Date(string="Dondurma Sonu", required=True, default=lambda self: fields.Date.today() + timedelta(days=7))
    freeze_days = fields.Integer(string="Donma Günləri", compute="_compute_freeze_days", store=True)
    
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
                
    @api.constrains('freeze_start_date', 'freeze_end_date')
    def _check_freeze_dates(self):
        for wizard in self:
            if wizard.freeze_start_date > wizard.freeze_end_date:
                raise ValidationError("Dondurma başlanğıc tarixi son tarixdən əvvəl olmalıdır!")
            
            if wizard.freeze_days < 1:
                raise ValidationError("Dondurma müddəti ən az 1 gün olmalıdır!")
                
    def action_confirm_freeze(self):
        """Abunəliyi dondur və xronologiya yarat"""
        self.ensure_one()
        
        # Yeni dondurma qeydini yarat
        freeze_record = self.env['badminton.lesson.freeze.genclik'].create({
            'lesson_id': self.lesson_id.id,
            'freeze_start_date': self.freeze_start_date,
            'freeze_end_date': self.freeze_end_date,
            'notes': self.notes or "Abunəlik donduruldu",
        })
        
        # Abunəliyi dondurul kimi işarələ
        self.lesson_id.state = 'frozen'
        
        # İnformasiya mesajı göstər
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurlu əməliyyat',
                'message': f'Abunəlik {self.freeze_days} gün müddətinə donduruldu.',
                'type': 'success',
                'sticky': False,
            }
        }
