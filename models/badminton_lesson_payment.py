# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class BadmintonLessonPayment(models.Model):
    _name = 'badminton.lesson.payment.genclik'
    _description = 'Badminton Dərs Ödənişi (Gənclik)'
    _order = 'payment_date desc'
    
    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Dərs Abunəliyi", required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='lesson_id.partner_id', string="Müştəri", store=True, readonly=True)
    
    # Ödəniş tarixi
    payment_date = fields.Date(string="Ödəniş Tarixi", required=True, default=fields.Date.today)
    
    # Ödəniş ayı (çox vacib - kassaya təsir edəcək)
    payment_month = fields.Selection([
        ('january', 'Yanvar'),
        ('february', 'Fevral'),
        ('march', 'Mart'),
        ('april', 'Aprel'),
        ('may', 'May'),
        ('june', 'İyun'),
        ('july', 'İyul'),
        ('august', 'Avqust'),
        ('september', 'Sentyabr'),
        ('october', 'Oktyabr'),
        ('november', 'Noyabr'),
        ('december', 'Dekabr'),
    ], string="Ödəniş Ayı", default=datetime.now().strftime('%B').lower(), required=True, help="Bu ayda ödəniş tarixi günündə kassaya təsir edəcək")
    
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
    
    def _compute_cash_date(self, payment_date, payment_month):
        """
        Kassaya yazılacaq tarixi hesabla:
        - payment_date-in GÜNÜ götürülür
        - payment_month-un AYI götürülür
        - Cari il istifadə olunur
        
        Məsələn: payment_date = 15 Yanvar 2025, payment_month = 'march'
        Nəticə: 15 Mart 2025
        """
        if not payment_date or not payment_month:
            return fields.Date.today()
        
        # Ay adlarını rəqəmə çevir
        month_mapping = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }
        
        day = payment_date.day
        month = month_mapping.get(payment_month, datetime.now().month)
        year = datetime.now().year
        
        # Əgər ay artıq keçibsə, növbəti ilə keç
        today = fields.Date.today()
        if month < today.month or (month == today.month and day < today.day):
            year = today.year + 1
        
        # Ayın son gününü yoxla (məsələn 31 Fevral olmaz)
        try:
            cash_date = datetime(year, month, day).date()
        except ValueError:
            # Əgər belə gün yoxdursa, ayın son günü götür
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            cash_date = datetime(year, month, min(day, last_day)).date()
        
        return cash_date
    
    @api.model
    def default_get(self, fields_list):
        """Default məbləğ olaraq lesson_fee götür"""
        res = super(BadmintonLessonPayment, self).default_get(fields_list)
        
        # Əgər context-də lesson_id varsa
        if self._context.get('default_lesson_id'):
            lesson = self.env['badminton.lesson.simple.genclik'].browse(self._context.get('default_lesson_id'))
            if lesson and 'amount' in fields_list:
                res['amount'] = lesson.lesson_fee
                
            # Default olaraq cari ayı təyin et
            if 'payment_month' in fields_list:
                current_month = datetime.now().month
                month_mapping = {
                    1: 'january', 2: 'february', 3: 'march', 4: 'april',
                    5: 'may', 6: 'june', 7: 'july', 8: 'august',
                    9: 'september', 10: 'october', 11: 'november', 12: 'december'
                }
                res['payment_month'] = month_mapping.get(current_month, 'january')
        
        return res
    
    @api.model
    def create(self, vals):
        """Ödəniş yaradılanda kassaya əlavə et"""
        payment = super(BadmintonLessonPayment, self).create(vals)
        
        # Kassaya əməliyyat əlavə et
        if payment.lesson_id and payment.amount > 0:
            month_names = dict(self._fields['payment_month'].selection)
            
            # Kassaya yazılacaq tarixi hesabla: 
            # lesson_id.payment_date-in günü + payment_month-un ayı + cari il
            cash_date = self._compute_cash_date(payment.lesson_id.payment_date, payment.payment_month)
            
            cash_flow = self.env['volan.cash.flow.genclik'].create({
                'name': f"Badminton dərs ödənişi (Gənclik): {payment.lesson_id.name} - {month_names.get(payment.payment_month, '')}",
                'date': cash_date,
                'amount': payment.amount,
                'transaction_type': 'income',
                'category': 'badminton_lesson',
                'partner_id': payment.partner_id.id,
                'related_model': 'badminton.lesson.payment.genclik',
                'related_id': payment.id,
                'notes': f"Ödəniş ayı: {month_names.get(payment.payment_month, '')} | Ödəniş günü: {payment.lesson_id.payment_date.day}"
            })
            payment.cash_flow_id = cash_flow.id
        
        return payment
    
    def write(self, vals):
        """Ödəniş dəyişdirildikdə kassanı da yenilə"""
        res = super(BadmintonLessonPayment, self).write(vals)
        
        # Əgər məbləğ və ya tarix dəyişibsə, kassanı yenilə
        if 'amount' in vals or 'payment_date' in vals or 'payment_month' in vals:
            for payment in self:
                if payment.cash_flow_id:
                    month_names = dict(self._fields['payment_month'].selection)
                    
                    # Kassaya yazılacaq tarixi yenidən hesabla
                    cash_date = self._compute_cash_date(payment.lesson_id.payment_date, payment.payment_month)
                    
                    payment.cash_flow_id.write({
                        'amount': payment.amount,
                        'date': cash_date,
                        'name': f"Badminton dərs ödənişi (Gənclik): {payment.lesson_id.name} - {month_names.get(payment.payment_month, '')}",
                        'notes': f"Ödəniş ayı: {month_names.get(payment.payment_month, '')} | Ödəniş günü: {payment.lesson_id.payment_date.day}"
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
        month_names = dict(self._fields['payment_month'].selection)
        for payment in self:
            name = f"{month_names.get(payment.payment_month, '')} - {payment.amount} AZN ({payment.payment_date})"
            result.append((payment.id, name))
        return result
