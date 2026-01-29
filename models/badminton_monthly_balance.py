# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BadmintonMonthlyBalance(models.Model):
    _name = 'badminton.monthly.balance.genclik'
    _description = 'Aylıq Badminton Paket Balansı'
    _order = 'expiry_date asc, create_date desc'
    _rec_name = 'name'

    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True, ondelete='cascade')
    sale_id = fields.Many2one('badminton.sale.genclik', string="Satış", ondelete='cascade')
    package_id = fields.Many2one('badminton.package.genclik', string="Paket")
    name = fields.Char(string="Ad", compute='_compute_name', store=True)

    initial_units = fields.Float(string="Başlanğıc Balans", required=True)
    remaining_units = fields.Float(string="Qalan Balans", required=True)
    deduction_factor = fields.Float(string="Sessiya Çarpanı", default=1.0)
    is_gedis_package = fields.Boolean(string="Gediş Paketi")

    expiry_date = fields.Date(string="Bitmə Tarixi", required=True)
    state = fields.Selection([
        ('active', 'Aktiv'),
        ('consumed', 'Tam İstifadə Edilib'),
        ('expired', 'Müddəti Bitib')
    ], string="Vəziyyət", default='active')

    @api.depends('package_id.name', 'remaining_units', 'deduction_factor', 'expiry_date', 'is_gedis_package')
    def _compute_name(self):
        for line in self:
            package_name = line.package_id.name or 'Aylıq Paket'
            details = []
            remaining = line.get_hours_available()
            details.append(f"Qalan: {remaining:g} saat")
            if line.is_gedis_package:
                details.append('Gediş Paketi')
            if line.expiry_date:
                details.append(f"Bitmə: {fields.Date.to_string(line.expiry_date)}")
            line.name = f"{package_name} ({', '.join(details)})"

    def name_get(self):
        return [(rec.id, rec.name or rec.package_id.name or 'Aylıq Paket') for rec in self]

    def get_hours_available(self):
        self.ensure_one()
        factor = self.deduction_factor or 1.0
        return self.remaining_units / factor if factor else self.remaining_units

    def consume_hours(self, hours_to_consume):
        """Azaldılan saatların ekvivalent vahidlərini qaytarır"""
        self.ensure_one()
        if hours_to_consume <= 0:
            return 0.0, self.remaining_units, self.remaining_units

        factor = self.deduction_factor or 1.0
        units_needed = hours_to_consume * factor
        before = self.remaining_units
        if units_needed > before:
            raise ValidationError('Aylıq paketdə kifayət qədər balans yoxdur')

        after = before - units_needed
        self.remaining_units = after
        if after <= 0:
            self.state = 'consumed'
        return units_needed, before, after

    @api.model
    def cron_expire_monthly_balances(self):
        today = fields.Date.today()
        expired_lines = self.search([
            ('state', '=', 'active'),
            ('expiry_date', '<', today),
            ('remaining_units', '>', 0)
        ])

        if not expired_lines:
            return True

        """ Close history
        history_model = self.env['badminton.balance.history.genclik']
        for line in expired_lines:
            before = line.remaining_units
            line.remaining_units = 0.0
            line.state = 'expired'
            history_model.create({
                'partner_id': line.partner_id.id,
                'sale_id': line.sale_id.id,
                'hours_used': before,
                'balance_before': before,
                'balance_after': 0.0,
                'transaction_type': 'expiry',
                'balance_channel': 'monthly',
                'monthly_line_id': line.id,
                'description': f"Aylıq paket müddəti bitdi ({fields.Date.to_string(line.expiry_date)})"
            })
        return True
        """
