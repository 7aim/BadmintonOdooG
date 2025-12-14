# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class BadmintonLessonPayment(models.Model):
    _name = 'badminton.lesson.payment.genclik'
    _description = 'Badminton Dərs Ödənişi (Gənclik)'
    _order = 'payment_date desc'
    
    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Dərs Abunəliyi", required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='lesson_id.partner_id', string="Müştəri", store=True, readonly=True)
    
    # Ödəniş
    payment_method_lesson = fields.Selection([
        ('cash', 'Nağd'),
        ('card', 'Kartdan karta'),
    ], string="Ödəniş Metodu", default='cash', required=True)

    payment_date = fields.Date(string="Aid olduğu ay", required=True, default=fields.Date.today,
                               help="Müştərinin real ödənişi etdiyi gün (informativ)")
    real_date = fields.Date(string="Ödəniş Tarixi", required=True, default=fields.Date.today,   
                            help="Kassaya mədaxilin düşəcəyi tarix (kassa bu tarixdə artacaq)")
    
    # Məbləğ
    amount = fields.Float(string="Məbləğ", required=True, compute='_compute_default_amount', store=True, readonly=False)
    
    # Kassa əməliyyatı
    cash_flow_id = fields.Many2one('volan.cash.flow.genclik', string="Kassa Əməliyyatı", readonly=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('lesson_id', 'lesson_id.lesson_fee')
    def _compute_default_amount(self):
        """Default məbləğ olaraq lesson_fee götür"""
        for payment in self:
            if payment.lesson_id and not payment.amount:
                payment.amount = payment.lesson_id.lesson_fee
            elif not payment.amount:
                payment.amount = 0.0
    
    @api.model
    def default_get(self, fields_list):
        """Default məbləğ olaraq lesson_fee götür"""
        res = super(BadmintonLessonPayment, self).default_get(fields_list)
        
        # Əgər context-də lesson_id varsa
        if self._context.get('default_lesson_id'):
            lesson = self.env['badminton.lesson.simple.genclik'].browse(self._context.get('default_lesson_id'))
            if lesson and 'amount' in fields_list:
                res['amount'] = lesson.lesson_fee
            if lesson and 'real_date' in fields_list and not res.get('real_date'):
                res['real_date'] = lesson.start_date or lesson.payment_date or fields.Date.today()
                
        return res
    
    @api.model
    def create(self, vals):
        """Ödəniş yaradılanda kassaya əlavə et"""
        lesson = self.env['badminton.lesson.simple.genclik'].browse(vals['lesson_id']) if vals.get('lesson_id') else False
        if lesson:
            default_due_date = lesson.start_date or lesson.payment_date or fields.Date.today()
            vals.setdefault('real_date', default_due_date)

        payment = super(BadmintonLessonPayment, self).create(vals)
        
        # Kassaya əməliyyat əlavə et
        if payment.lesson_id and payment.amount > 0:
            cash_date = payment.real_date or payment.payment_date or fields.Date.today()
            
            cash_flow = self.env['volan.cash.flow.genclik'].create({
                'name': f"Badminton dərs ödənişi: {payment.lesson_id.name} - {cash_date}",
                'date': cash_date,
                'amount': payment.amount,
                'transaction_type': 'income',
                'category': 'badminton_lesson',
                'sport_type': 'badminton',
                'partner_id': payment.partner_id.id,
                'related_model': 'badminton.lesson.payment.genclik',
                'related_id': payment.id,
                'notes': f"Ödənilən tarix: {payment.payment_date or '-'}"
            })
            payment.cash_flow_id = cash_flow.id
        
        return payment

    def write(self, vals):
        """Ödəniş dəyişdirildikdə kassanı da yenilə"""
        res = super(BadmintonLessonPayment, self).write(vals)
        
        # Əgər məbləğ və ya kassaya düşmə tarixi dəyişibsə, kassanı yenilə
        if 'amount' in vals or 'real_date' in vals:
            for payment in self:
                if payment.cash_flow_id:
                    cash_date = payment.real_date or payment.payment_date or fields.Date.today()
                    
                    payment.cash_flow_id.write({
                        'amount': payment.amount,
                        'date': cash_date,
                        'name': f"Badminton dərs ödənişi: {payment.lesson_id.name} - {cash_date}",
                        'sport_type': 'badminton',
                        'category': 'badminton_lesson',
                        'notes': f"Ödənilən tarix: {payment.payment_date or '-'}"
                    })
        
        return res
    
    def unlink(self):
        """Ödəniş silinərkən kassadan da sil"""
        # Əvvəlcə kassa əməliyyatını sil
        for payment in self:
            if payment.cash_flow_id:
                payment.cash_flow_id.unlink()
        
        return super(BadmintonLessonPayment, self).unlink()
    
    def name_get(self):
        """Display name"""
        result = []
        for payment in self:
            real_date = payment.real_date or payment.payment_date or '-'
            paid_date = payment.payment_date or '-'
            name = f"{real_date} - {payment.amount} AZN (Ödənilən: {paid_date})"
            result.append((payment.id, name))
        return result