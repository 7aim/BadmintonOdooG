# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta
import base64
import os

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
    
    # Çap sayı (tracking üçün)
    print_count = fields.Integer(string="Çap Sayı", default=0, readonly=True)
    last_print_date = fields.Datetime(string="Son Çap Tarixi", readonly=True)

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
                res['real_date'] = lesson.payment_date or fields.Date.today()
                
        return res
    
    @api.model
    def create(self, vals):
        """Ödəniş yaradılanda kassaya əlavə et"""
        lesson = self.env['badminton.lesson.simple.genclik'].browse(vals['lesson_id']) if vals.get('lesson_id') else False
        if lesson:
            default_due_date = lesson.payment_date or fields.Date.today()
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

        # Admin olmayan userlər real_date-i update edə bilməz
        if 'real_date' in vals and not self.env.user.has_group('base.group_system'):
            vals.pop('real_date')

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
        for payment in self:
            # Kassa əməliyyatını tap və sil
            cash_flows = self.env['volan.cash.flow.genclik'].search([
                ('related_model', '=', 'badminton.lesson.payment.genclik'),
                ('related_id', '=', payment.id)
            ])
            if cash_flows:
                # related_model-i sıfırla ki, unlink qadağası işləməsin
                cash_flows.write({'related_model': False, 'related_id': False})
                cash_flows.unlink()
            
            # Əski sistemlə uyğunluq üçün
            if payment.cash_flow_id:
                payment.cash_flow_id.write({'related_model': False, 'related_id': False})
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


    def action_print_receipt(self):
        """Ödəniş çekini birbaşa çap et"""
        self.ensure_one()
        
        # Çap sayını artır
        self.sudo().write({
            'print_count': self.print_count + 1,
            'last_print_date': fields.Datetime.now()
        })
        
        # Report-u birbaşa qaytır
        return {
            'type': 'ir.actions.report',
            'report_name': 'volan_genclikk.report_badminton_payment_receipt_document',
            'report_type': 'qweb-pdf',
        }
    
    def get_badminton_logo(self):
        """Badminton logo-nu base64 formatında qaytarır"""
        try:
            # Modul yolunu tap
            module_path = os.path.dirname(os.path.dirname(__file__))
            logo_path = os.path.join(module_path, 'static', 'description', 'icon.png')
            
            # Faylı oxu və base64-ə çevir
            with open(logo_path, 'rb') as img_file:
                return base64.b64encode(img_file.read())
        except Exception:
            return False

    def get_amount_in_words(self):
        """Məbləği yazı ilə qaytarır"""
        self.ensure_one()
        amount = int(self.amount)
        
        ones = ['', 'bir', 'iki', 'üç', 'dörd', 'beş', 'altı', 'yeddi', 'səkkiz', 'doqquz']
        tens = ['', 'on', 'iyirmi', 'otuz', 'qırx', 'əlli', 'altmış', 'yetmiş', 'səksən', 'doxsan']
        hundreds = ['', 'yüz', 'iki yüz', 'üç yüz', 'dörd yüz', 'beş yüz', 'altı yüz', 'yeddi yüz', 'səkkiz yüz', 'doqquz yüz']
        
        if amount == 0:
            return 'sıfır manat'
        
        result = []
        
        # Yüzlük
        if amount >= 100:
            result.append(hundreds[amount // 100])
            amount %= 100
        
        # Onluq
        if amount >= 10:
            result.append(tens[amount // 10])
            amount %= 10
        
        # Birlik
        if amount > 0:
            result.append(ones[amount])
        
        return ' '.join(result) + ' manat'
    
    def get_receipt_number(self):
        """Qəbz nömrəsini qaytarır - ödəniş ID və ay baş hərfi əsasında"""
        self.ensure_one()
        
        # Ayın baş hərfini götür
        month_prefix = {
            1: 'Y',   # Yanvar
            2: 'F',   # Fevral
            3: 'M',   # Mart
            4: 'A',   # Aprel
            5: 'M',   # May
            6: 'İ',   # İyun
            7: 'İ',   # İyul
            8: 'A',   # Avqust
            9: 'S',   # Sentyabr
            10: 'O',  # Oktyabr
            11: 'N',  # Noyabr
            12: 'D',  # Dekabr
        }
        
        # payment_date-dən ayı götür
        month = self.payment_date.month if self.payment_date else 1
        prefix = month_prefix.get(month, 'Y')
        
        return f"{prefix}{str(self.id).zfill(5)}"
    
    def get_service_description(self):
        """Xidmət təsvirini qaytarır"""
        self.ensure_one()
        # Ay adlarını Azərbaycan dilində
        months_az = {
            '01': 'Yanvar', '02': 'Fevral', '03': 'Mart', '04': 'Aprel',
            '05': 'May', '06': 'Iyun', '07': 'Iyul', '08': 'Avqust',
            '09': 'Sentyabr', '10': 'Oktyabr', '11': 'Noyabr', '12': 'Dekabr'
        }
        
        month_num = self.payment_date.strftime('%m')
        month_name = months_az.get(month_num, '')
        
        return f"{month_name} ayı üçün badminton məşqləri"