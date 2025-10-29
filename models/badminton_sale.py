# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class BadmintonSale(models.Model):
    _name = 'badminton.sale.genclik'
    _description = 'Badminton Satışı'
    _order = 'create_date desc'
    
    name = fields.Char(string="Satış Nömrəsi", readonly=True, default="Yeni")
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
    
    # Satış məlumatları
    hours_quantity = fields.Integer(string="Saat Sayı", required=True, default=1)
    unit_price = fields.Float(string="Saatlıq Qiymət", default=8, store=True)
    total_amount = fields.Float(string="Ümumi Məbləğ", compute='_compute_total_amount', store=True)
    
    payment_date = fields.Datetime(string="Ödəniş Tarixi")
    payment_method = fields.Selection([
        ('cash', 'Nağd'),
        ('card', 'Kartdan karta'),
        ('abonent', 'Abunəçi'),
    ], string="Ödəniş Metodu")
    
    # Vəziyyət
    state = fields.Selection([
        ('draft', 'Layihə'),
        ('confirmed', 'Təsdiqlənib'),
        ('paid', 'Ödənilib'),
        ('cancelled', 'Ləğv Edilib')
    ], default='draft', string="Vəziyyət")
    
    # Müştəri hesabı məlumatları
    credited_hours = fields.Integer(string="Hesaba Əlavə Edilən Saatlar", default=0)
    
    # Tarix məlumatları
    sale_date = fields.Date(string="Satış Tarixi", default=fields.Date.today)
    expiry_date = fields.Date(string="Son İstifadə Tarixi", compute='_compute_expiry_date', store=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('hours_quantity', 'unit_price')
    def _compute_total_amount(self):
        for sale in self:
            if sale.customer_type == 'child':  # Uşaqlar üçün
                if sale.package_type == 'single':
                    sale.total_amount = sale.hours_quantity * sale.unit_price
                elif sale.package_type == 'package_8':
                    sale.total_amount = 75.0  # 8 giriş paketi: 75 AZN
                elif sale.package_type == 'package_12':
                    sale.total_amount = 105.0  # 12 giriş paketi: 105 AZN
            else:  # Böyüklər üçün
                if sale.package_type == 'single':
                    sale.total_amount = sale.hours_quantity * sale.unit_price
                elif sale.package_type == 'package_8':
                    sale.total_amount = 55.0  # 8 giriş paketi: 55 AZN
                elif sale.package_type == 'package_12':
                    sale.total_amount = 85.0  # 12 giriş paketi: 85 AZN
    
    @api.depends('sale_date', 'package_type')
    def _compute_expiry_date(self):
        for sale in self:
            if sale.sale_date:
                # Paketlərə görə son istifadə tarixini müəyyən et
                if sale.package_type in ['package_8', 'package_12']:
                    # Aylıq paketlər üçün 30 gün
                    sale.expiry_date = sale.sale_date + timedelta(days=30)
                else:
                    # Tək saatlar üçün 6 ay
                    sale.expiry_date = sale.sale_date + timedelta(days=180)
            else:
                sale.expiry_date = False
    
    @api.depends('package_type')
    def _compute_is_package(self):
        """Seçilən paket növündən asılı olaraq is_package sahəsini təyin et"""
        for sale in self:
            sale.is_package = sale.package_type in ['package_8', 'package_12']
    
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
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'Yeni') == 'Yeni':
            vals['name'] = self.env['ir.sequence'].next_by_code('badminton.sale.genclik') or 'BS001'
        
        sale = super(BadmintonSale, self).create(vals)
        
        # Əgər satış 'paid' vəziyyətində yaradılırsa, dərhal balansı artır və kassaya əlavə et
        if sale.state == 'paid':
            # Kassaya əməliyyatı əlavə et
            self.env['volan.cash.flow.genclik'].create({
                'name': f"Badminton satışı: {sale.name}",
                'date': fields.Date.today(),
                'amount': sale.total_amount,
                'transaction_type': 'income',
                'category': 'badminton_sale',
                'partner_id': sale.partner_id.id,
                'related_model': 'badminton.sale.genclik',
                'related_id': sale.id,
                'notes': f"{sale.hours_quantity} saat, {sale.unit_price} AZN/saat"
            })
            
            # Müştəri hesabına saatları əlavə et
            sale._add_hours_to_customer()
            sale.credited_hours = sale.hours_quantity
            
        return sale
    
    def action_confirm(self):
        """Satışı təsdiqləyir"""
        for sale in self:
            if sale.state == 'draft':
                sale.state = 'confirmed'
    
    def action_mark_paid(self):
        """Ödənişi qeyd edir və müştəri hesabına saatları əlavə edir"""
        for sale in self:
            if sale.state in ['draft', 'confirmed'] and sale.credited_hours == 0:
                sale.state = 'paid'
                sale.payment_date = fields.Datetime.now()
                
                # Kassaya əməliyyatı əlavə et
                self.env['volan.cash.flow.genclik'].create({
                    'name': f"Badminton satışı: {sale.name}",
                    'date': fields.Date.today(),
                    'amount': sale.total_amount,
                    'transaction_type': 'income',
                    'category': 'badminton_sale',
                    'partner_id': sale.partner_id.id,
                    'related_model': 'badminton.sale.genclik',
                    'related_id': sale.id,
                    'notes': f"{sale.hours_quantity} saat, {sale.unit_price} AZN/saat"
                })
                
                # Müştəri hesabına saatları əlavə et
                sale._add_hours_to_customer()
                sale.credited_hours = sale.hours_quantity
    
    def action_cancel(self):
        """Satışı ləğv edir"""
        for sale in self:
            if sale.state in ['draft', 'confirmed']:
                sale.state = 'cancelled'
    
    def _add_hours_to_customer(self):
        """Müştəri hesabına badminton saatlarını əlavə edir"""
        for sale in self:
            # Əgər artıq hesaba əlavə edilmişsə, təkrar etmə
            if sale.credited_hours > 0:
                return
                
            # Müştərinin badminton balansını yenilə
            partner = sale.partner_id
            current_balance = partner.badminton_balance or 0
            partner.badminton_balance = current_balance + sale.hours_quantity
            
            # Tarixçə yaradırıq
            self.env['badminton.balance.history.genclik'].create({
                'partner_id': partner.id,
                'sale_id': sale.id,
                'hours_added': sale.hours_quantity,
                'balance_before': current_balance,
                'balance_after': current_balance + sale.hours_quantity,
                'transaction_type': 'purchase',
                'description': f"Badminton saatları alışı: {sale.name}"
            })


class BadmintonBalanceHistory(models.Model):
    _name = 'badminton.balance.history.genclik'
    _description = 'Badminton Balans Tarixçəsi'
    _order = 'create_date desc'
    
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    sale_id = fields.Many2one('badminton.sale.genclik', string="Satış")
    session_id = fields.Many2one('badminton.session.genclik', string="Sessiya")
    
    transaction_type = fields.Selection([
        ('purchase', 'Alış'),
        ('usage', 'İstifadə'),
        ('extension', 'Uzatma'),
        ('refund', 'Geri Ödəmə'),
        ('adjustment', 'Düzəliş')
    ], string="Əməliyyat Növü", required=True)

    hours_added = fields.Integer(string="Alındı", default=0)
    hours_used = fields.Integer(string="İstifadə", default=0)
    balance_before = fields.Integer(string="Əvvəlki Balans")
    balance_after = fields.Integer(string="Balans")
    
    description = fields.Text(string="Təsvir")
    transaction_date = fields.Datetime(string="Əməliyyat Tarixi", default=fields.Datetime.now)
