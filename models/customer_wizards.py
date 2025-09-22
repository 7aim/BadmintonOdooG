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
    
    # Müştəri növü və paket
    customer_type = fields.Selection([
        ('child', 'Uşaq'),
        ('adult', 'Böyük')
    ], string="Müştəri Növü", required=True, default='adult')
    
    package_type = fields.Selection([
        ('single', 'Tək Saat'),
        ('package_8', '8 Giriş (Aylıq)'),
        ('package_12', '12 Giriş (Aylıq)')
    ], string="Paket Növü", required=True, default='single')
    
    is_package = fields.Boolean(string="Paketdir", compute='_compute_is_package', store=True)
    
    hours_quantity = fields.Integer(string="Saat Sayı", required=True, default=1)
    unit_price = fields.Float(string="Saatlıq Qiymət", default=8.0, store=True)
    total_amount = fields.Float(string="Ümumi Məbləğ", compute='_compute_total_amount', store=True)
    
    # Müştərinin cari balansını göstər
    current_balance = fields.Integer(string="Cari Balans", related='partner_id.badminton_balance', readonly=True)
    
    @api.depends('package_type')
    def _compute_is_package(self):
        """Seçilən paket növündən asılı olaraq is_package sahəsini təyin et"""
        for wizard in self:
            wizard.is_package = wizard.package_type in ['package_8', 'package_12']
    
    @api.depends('hours_quantity', 'unit_price', 'customer_type', 'package_type')
    def _compute_total_amount(self):
        for wizard in self:
            if wizard.customer_type == 'child':  # Uşaqlar üçün
                if wizard.package_type == 'single':
                    wizard.total_amount = wizard.hours_quantity * 15.0
                elif wizard.package_type == 'package_8':
                    wizard.total_amount = 75.0  # 8 giriş paketi: 75 AZN
                elif wizard.package_type == 'package_12':
                    wizard.total_amount = 105.0  # 12 giriş paketi: 105 AZN
            else:  # Böyüklər üçün
                if wizard.package_type == 'single':
                    wizard.total_amount = wizard.hours_quantity * 8.0
                elif wizard.package_type == 'package_8':
                    wizard.total_amount = 55.0  # 8 giriş paketi: 55 AZN
                elif wizard.package_type == 'package_12':
                    wizard.total_amount = 85.0  # 12 giriş paketi: 85 AZN
    
    @api.onchange('customer_type', 'package_type')
    def _onchange_customer_package_type(self):
        """Müştəri növü və ya paket növü dəyişəndə qiymətləri yenilə"""
        if self.customer_type == 'child':  # Uşaqlar üçün
            if self.package_type == 'single':
                self.unit_price = 15.0
                self.hours_quantity = 1
            elif self.package_type == 'package_8':
                self.unit_price = 9.375
                self.hours_quantity = 8
            elif self.package_type == 'package_12':
                self.unit_price = 8.75
                self.hours_quantity = 12
        else:  # Böyüklər üçün
            if self.package_type == 'single':
                self.unit_price = 8.0
                self.hours_quantity = 1
            elif self.package_type == 'package_8':
                self.unit_price = 6.875
                self.hours_quantity = 8
            elif self.package_type == 'package_12':
                self.unit_price = 7.083
                self.hours_quantity = 12
    
    def action_create_sale(self):
        """Satış yaradır və dərhal balansı artırır"""
        if not self.partner_id or self.hours_quantity <= 0:
            raise ValidationError("Zəhmət olmasa bütün sahələri doldurun!")
        
        # Badminton satışı yaradırıq (dərhal ödənilib statusunda)
        sale = self.env['badminton.sale.genclik'].create({
            'partner_id': self.partner_id.id,
            'customer_type': self.customer_type,
            'package_type': self.package_type,
            'hours_quantity': self.hours_quantity,
            'unit_price': self.unit_price,
            'state': 'paid',  # Dərhal ödənilib
            'payment_date': fields.Datetime.now(),
        })
        
        # Balans create funksiyasında avtomatik artırılacaq
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'{self.partner_id.name} üçün {self.hours_quantity} saat badminton satışı tamamlandı! '
                          f'Yeni balans: {self.partner_id.badminton_balance} saat',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
