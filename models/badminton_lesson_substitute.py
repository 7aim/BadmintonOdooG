# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class BadmintonLessonSubstitute(models.Model):
    _name = 'badminton.lesson.substitute.genclik'
    _description = 'Badminton Əvəzedici Dərs'
    _order = 'substitute_date desc, id desc'

    lesson_id = fields.Many2one(
        'badminton.lesson.simple.genclik',
        string="Abunəlik",
        required=True,
        ondelete='cascade'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Müştəri",
        related='lesson_id.partner_id',
        store=True,
        readonly=True
    )
    origin_group_ids = fields.Many2many(
        'badminton.group.genclik',
        string="Cari Qruplar",
        related='lesson_id.group_ids',
        readonly=True
    )
    group_id = fields.Many2one(
        'badminton.group.genclik',
        string="Əvəzedici Qrup",
        required=True,
        domain=[('is_active', '=', True)]
    )
    schedule_id = fields.Many2one(
        'badminton.group.schedule.genclik',
        string="Əvəzedici Qrafik",
        domain="[('group_id', '=', group_id), ('is_active', '=', True)]"
    )
    substitute_date = fields.Date(
        string="Tarix",
        required=True,
        default=fields.Date.context_today
    )
    day_of_week = fields.Selection(
        related='schedule_id.day_of_week',
        string="Həftənin Günü",
        store=True,
        readonly=True
    )
    start_time = fields.Float(
        related='schedule_id.start_time',
        string="Başlanğıc Vaxtı",
        store=True,
        readonly=True
    )
    end_time = fields.Float(
        related='schedule_id.end_time',
        string="Bitmə Vaxtı",
        store=True,
        readonly=True
    )
    state = fields.Selection([
        ('pending', 'Gözləyir'),
        ('used', 'İstifadə olundu'),
        ('cancelled', 'Ləğv edildi')
    ], string="Vəziyyət", default='pending', required=True)
    
    note = fields.Text(string="Qeyd")

    @api.constrains('substitute_date', 'lesson_id')
    def _check_substitute_date(self):
        """Əvəzedici dərsin tarixi dərs aktiv olduğu zaman olmalıdır"""
        for record in self:
            if record.lesson_id:
                if record.substitute_date < record.lesson_id.start_date:
                    raise ValidationError(
                        "Əvəzedici dərsin tarixi abunəlik başlama tarixindən əvvəl ola bilməz!"
                    )

    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup dəyişdikdə qrafiki təmizlə"""
        if self.group_id:
            self.schedule_id = False
            return {
                'domain': {
                    'schedule_id': [
                        ('group_id', '=', self.group_id.id),
                        ('is_active', '=', True)
                    ]
                }
            }

    def action_use(self):
        """Əvəzedici dərsi istifadə edilmiş kimi qeyd et"""
        self.ensure_one()
        if self.state == 'pending':
            self.state = 'used'

    def action_cancel(self):
        """Əvəzedici dərsi ləğv et"""
        self.ensure_one()
        if self.state == 'pending':
            self.state = 'cancelled'
