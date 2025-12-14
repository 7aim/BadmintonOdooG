# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BadmintonSessionExtendWizard(models.TransientModel):
    _name = 'badminton.session.extend.wizard.genclik'
    _description = 'Sessiya Uzatma Sihirbazı'

    session_id = fields.Many2one('badminton.session.genclik', string="Sessiya", required=True)
    partner_id = fields.Many2one(related='session_id.partner_id', string="Müştəri", readonly=True)
    current_balance = fields.Integer(related='partner_id.badminton_balance', string="Mövcud Balans", readonly=True)
    monthly_balance_hours = fields.Float(related='partner_id.monthly_balance_hours', string="Aylıq Balans (saat)", readonly=True)
    extend_hours = fields.Float(string="Uzatma Saatı", default=1.0, required=True)

    def extend_session(self):
        """Sessiyanı seçilən saat qədər uzat"""
        if self.session_id and self.extend_hours > 0:
            self.session_id.extend_session(self.extend_hours)
            return {
                'type': 'ir.actions.client',
                'tag': 'reload'
            }
        else:
            raise ValidationError("Uzatma saatı 0-dan böyük olmalıdır!")
