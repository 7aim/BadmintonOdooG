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
    
    # Paket seçimi
    package_id = fields.Many2one('badminton.package.genclik', string="Paket")
    is_student = fields.Boolean(string="Tələbədir", default=False)
    
    # Sadə satış
    customer_type = fields.Selection([
        ('child', 'Uşaq'),
        ('adult', 'Böyük')
    ], string="Müştəri Növü", default='adult')
    hours_quantity = fields.Integer(string="Saat Sayı", default=1)
    unit_price = fields.Float(string="Saat Başı Qiymət", default=8.0)
    total_amount = fields.Float(string="Ümumi Məbləğ", store=True)
    
    # Müştərinin cari balansını göstər
    current_balance = fields.Integer(string="Cari Balans", related='partner_id.badminton_balance', readonly=True)
    
    @api.onchange('package_id', 'customer_type', 'is_student')
    def _onchange_package(self):
        """Paket və müştəri növünə görə qiyməti təyin et"""
        if self.package_id:
            if self.is_student:
                self.total_amount = self.package_id.student_price
            elif self.customer_type == 'child':
                self.total_amount = self.package_id.child_price
            else:
                self.total_amount = self.package_id.adult_price
    
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
    
    def _calculate_total(self):
        """Ümumi məbləği hesabla"""
        if self.hours_quantity and self.unit_price:
            self.total_amount = self.hours_quantity * self.unit_price
    
    def action_create_sale(self):
        """Satış yaradır və dərhal balansı artırır"""
        if not self.partner_id:
            raise ValidationError("Zəhmət olmasa müştəri seçin!")
        
        if not self.total_amount or self.total_amount <= 0:
            raise ValidationError("Ümumi məbləğ 0-dan böyük olmalıdır!")
        
        if self.package_id:
            # Paket sistemi
            balance_to_add = self.package_id.balance_count
            sale_data = {
                'partner_id': self.partner_id.id,
                'customer_type': self.customer_type,
                'package_type': 'single',
                'hours_quantity': balance_to_add,
                'unit_price': self.total_amount,
                'total_amount': self.total_amount,
                'state': 'paid',
                'payment_date': fields.Datetime.now(),
            }
        else:
            # Sadə sistem - saat sayı ilə
            balance_to_add = self.hours_quantity
            sale_data = {
                'partner_id': self.partner_id.id,
                'customer_type': self.customer_type,
                'package_type': 'single',
                'hours_quantity': self.hours_quantity,
                'unit_price': self.unit_price,
                'total_amount': self.total_amount,
                'state': 'paid',
                'payment_date': fields.Datetime.now(),
            }
        
        # Badminton satışı yaradırıq
        sale = self.env['badminton.sale.genclik'].create(sale_data)
        
        # Balansı artırırıq
        self.partner_id.badminton_balance += balance_to_add
        
        package_name = self.package_id.name if self.package_id else f"{self.total_amount} AZN"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'{self.partner_id.name} üçün {package_name} satışı tamamlandı! '
                          f'Yeni balans: {self.partner_id.badminton_balance} saat',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
