# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CustomerLookupWizard(models.TransientModel):
    _name = 'customer.lookup.wizard'
    _description = 'Müştəri Axtarış Sihirbazı'
    
    search_term = fields.Char(string="Axtarış", required=True, help="Müştəri adı və ya telefon nömrəsi")
    customer_ids = fields.Many2many('res.partner', string="Tapılan Müştərilər")
    
    @api.onchange('search_term')
    def _onchange_search_term(self):
        if self.search_term and len(self.search_term) >= 2:
            domain = [
                '|', '|',
                ('name', 'ilike', self.search_term),
                ('qr', 'ilike', self.search_term),
                ('phone', 'ilike', self.search_term),
                ('mobile', 'ilike', self.search_term)
            ]
            customers = self.env['res.partner'].search(domain, limit=10)
            self.customer_ids = [(6, 0, customers.ids)]
        else:
            self.customer_ids = [(5, 0, 0)]
    
    def action_view_customer(self):
        """Seçilən müştərinin səhifəsini aç"""
        if len(self.customer_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Müştəri Məlumatları',
                'res_model': 'res.partner',
                'res_id': self.customer_ids[0].id,
                'view_mode': 'form',
                'target': 'current'
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Müştərilər',
                'res_model': 'res.partner',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.customer_ids.ids)],
                'target': 'current'
            }

class BadmintonSaleWizard(models.TransientModel):
    _name = 'badminton.sale.wizard.genclik'
    _description = 'Badminton Satış Sihirbazı'
    
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    
    # Paket seçimi - yalnız satış paketləri
    package_id = fields.Many2one('badminton.package.genclik', string="Paket", 
                                  domain="[('package_type', 'in', ['sale', 'monthly']), ('active', '=', True)]")
    is_gedis_package = fields.Boolean(string="Gediş Paketi", related='package_id.is_gedis_package', readonly=True)
        
    # Sadə satış
    customer_type = fields.Selection([
        ('child', 'Uşaq'),
        ('adult', 'Böyük')
    ], string="Müştəri Növü", default='adult')
    hours_quantity = fields.Integer(string="Saat Sayı", default=1)
    unit_price = fields.Float(string="Saat Başı Qiymət", default=8.0)
    
    # Qiymət məlumatları
    original_price = fields.Float(string="Endirimsiz Qiymət", readonly=True)
    discount_percent = fields.Float(string="Endirim (%)", readonly=True)
    total_amount = fields.Float(string="Ümumi Məbləğ", store=True)
    
    # Ödəniş məlumatları
    payment_method = fields.Selection([
        ('cash', 'Nağd'),
        ('card', 'Kartdan karta'),
        ('abonent', 'Abunəçi'),
    ], default='cash', string="Ödəniş Metodu")

    # Müştərinin cari balansını göstər
    current_balance = fields.Integer(string="Cari Balans", related='partner_id.badminton_balance', readonly=True)
    monthly_balance_hours = fields.Float(string="Aylıq Balans (saat)", related='partner_id.monthly_balance_hours', readonly=True)
    
    # Depozit məlumatları
    customer_deposit_balance = fields.Float(string="Müştəri Depoziti", related='partner_id.badminton_deposit_balance', readonly=True)
    deposit_used = fields.Float(string="İstifadə Edilən Depozit", default=0.0, help="Bu satışda istifadə edilən depozit məbləği")
    amount_to_pay = fields.Float(string="Ödəniləcək Məbləğ", compute='_compute_amount_to_pay', store=True, help="Depozit nəzərə alındıqdan sonra ödəniləcək məbləğ")
    amount_paid = fields.Float(string="Ödənilən Məbləğ", default=0.0, help="Müştərinin faktiki ödədiyi məbləğ")
    deposit_added = fields.Float(string="Depozitə Əlavə", default=0.0, help="Artıq ödənişdən depozitə əlavə edilən məbləğ")
    
    @api.depends('total_amount', 'partner_id.badminton_deposit_balance', 'deposit_used')
    def _compute_amount_to_pay(self):
        """Depozit nəzərə alınaraq ödəniləcək məbləği hesabla"""
        for wizard in self:
            if wizard.total_amount and wizard.partner_id:
                available_deposit = wizard.partner_id.badminton_deposit_balance
                # Maksimum istifadə edilə biləcək depozit məbləği
                max_deposit = min(available_deposit, wizard.total_amount)
                wizard.amount_to_pay = wizard.total_amount - max_deposit
            else:
                wizard.amount_to_pay = wizard.total_amount or 0.0
    
    @api.onchange('amount_to_pay')
    def _onchange_amount_to_pay(self):
        """amount_to_pay dəyişəndə amount_paid-i avtomatik yenilə"""
        if self.amount_to_pay:
            self.amount_paid = self.amount_to_pay
    
    @api.onchange('package_id', 'customer_type')
    def _onchange_package(self):
        """Paket və müştəri növünə görə qiyməti təyin et"""
        if self.package_id:
            # Paketdən balansı hours_quantity-yə yaz
            self.hours_quantity = self.package_id.balance_count
            
            # Endirimsiz qiyməti təyin et
            if self.customer_type == 'child':
                self.original_price = self.package_id.child_price
            else:
                self.original_price = self.package_id.adult_price
            
            # Endirim faizini təyin et
            self.discount_percent = self.package_id.discount_percent
            
            # Endirimli qiyməti hesabla
            if self.discount_percent > 0:
                discount_amount = self.original_price * (self.discount_percent / 100)
                self.total_amount = self.original_price - discount_amount
            else:
                self.total_amount = self.original_price
        else:
            self.original_price = 0
            self.discount_percent = 0
    
    @api.onchange('customer_type')
    def _onchange_customer_type(self):
        """Müştəri növünə görə qiyməti təyin et"""
        if not self.package_id:
            if self.customer_type == 'child':
                self.unit_price = 15.0
            else:
                self.unit_price = 8.0
            self._calculate_total()
    
    @api.onchange('hours_quantity', 'unit_price')
    def _onchange_price_fields(self):
        """Saat sayı və ya qiymət dəyişəndə ümumi məbləği hesabla"""
        if not self.package_id:
            self._calculate_total()
    
    @api.onchange('amount_paid', 'total_amount', 'partner_id')
    def _onchange_amount_paid(self):
        """Ödənilən məbləğ dəyişəndə depozit istifadə və əlavəsini hesabla"""
        if self.partner_id and self.total_amount:
            available_deposit = self.partner_id.badminton_deposit_balance
            
            if self.amount_paid >= self.total_amount:
                # Müştəri lazım olandan çox ödəyir
                # Əvvəlcə depoziti istifadə edirik
                self.deposit_used = min(available_deposit, self.total_amount)
                # Qalan məbləği depozitə əlavə edirik
                self.deposit_added = self.amount_paid - (self.total_amount - self.deposit_used)
            elif self.amount_paid > 0:
                # Müştəri qismən ödəyir, depozitdən istifadə edəcəyik
                remaining = self.total_amount - self.amount_paid
                self.deposit_used = min(available_deposit, remaining)
                self.deposit_added = 0.0
            else:
                # Heç bir ödəniş yoxdur, maksimum depozit istifadə ediləcək
                self.deposit_used = min(available_deposit, self.total_amount)
                self.deposit_added = 0.0
    
    def _calculate_total(self):
        """Ümumi məbləği hesabla"""
        if self.hours_quantity and self.unit_price:
            self.total_amount = self.hours_quantity * self.unit_price
    
    def action_create_sale(self):
        """Satış yaradır və dərhal balansı artırır"""
        if self.total_amount <= 0:
            raise ValidationError("Ümumi məbləğ 0-dan böyük olmalıdır!")
        if not self.partner_id:
            raise ValidationError("Zəhmət olmasa müştəri seçin!")
        
        # Depozit məlumatlarını YENIDƏN hesabla (onchange UI-da qalır, database-ə yazılmır)
        actual_amount_paid = self.amount_paid or 0.0
        available_deposit = self.partner_id.badminton_deposit_balance
        
        if actual_amount_paid >= self.total_amount:
            deposit_used = min(available_deposit, self.total_amount)
            deposit_added = actual_amount_paid - (self.total_amount - deposit_used)
        elif actual_amount_paid > 0:
            remaining = self.total_amount - actual_amount_paid
            deposit_used = min(available_deposit, remaining)
            deposit_added = 0.0
        else:
            deposit_used = min(available_deposit, self.total_amount)
            deposit_added = 0.0
        
        amount_to_pay = self.total_amount - deposit_used
        
        # Wizard field-lərini BİRBAŞA badminton.sale-ə ötür
        if self.package_id:
            # Paket sistemi
            sale_data = {
                'partner_id': self.partner_id.id,
                'customer_type': self.customer_type,
                'package_type': 'single',
                'package_id': self.package_id.id,
                'hours_quantity': self.package_id.balance_count,
                'unit_price': self.total_amount,
                'total_amount': self.total_amount,
                'state': 'paid',
                'payment_date': fields.Datetime.now(),
                'payment_method': self.payment_method,
                # Depozit məlumatları - HESABLANMIŞ dəyərlər
                'amount_paid': actual_amount_paid,
                'amount_to_pay': amount_to_pay,
                'deposit_used': deposit_used,
                'deposit_added': deposit_added,
            }
        else:
            # Sadə sistem
            sale_data = {
                'partner_id': self.partner_id.id,
                'customer_type': self.customer_type,
                'package_type': 'single',
                'hours_quantity': self.hours_quantity,
                'unit_price': self.unit_price,
                'total_amount': self.total_amount,
                'state': 'paid',
                'payment_date': fields.Datetime.now(),
                'payment_method': self.payment_method,
                'package_id': False,
                # Depozit məlumatları - HESABLANMIŞ dəyərlər
                'amount_paid': actual_amount_paid,
                'amount_to_pay': amount_to_pay,
                'deposit_used': deposit_used,
                'deposit_added': deposit_added,
            }
        
        # Badminton satışı yaradırıq
        sale = self.env['badminton.sale.genclik'].create(sale_data)
        
        # QEYD: Balans avtomatik artırılır badminton.sale modelinin create() metodunda
        # çünki state='paid' olaraq yaradılır
        
        package_name = self.package_id.name if self.package_id else f"{self.total_amount} AZN"
        
        normal_balance = self.partner_id.badminton_balance
        monthly_balance = self.partner_id.monthly_balance_hours

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': (f'{self.partner_id.name} üçün {package_name} satışı tamamlandı! '
                            f'Normal: {normal_balance} saat | Aylıq: {monthly_balance} saat'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
