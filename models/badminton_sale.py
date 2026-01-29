# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class BadmintonSale(models.Model):
    _name = 'badminton.sale.genclik'
    _description = 'Badminton Satışı'
    _order = 'create_date desc'
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Satış nömrəsi unikal olmalıdır!')
    ]
    
    name = fields.Char(string="Satış Nömrəsi", readonly=True, default="Yeni", copy=False)
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    package_id = fields.Many2one('badminton.package.genclik', string="Paket")
    
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
    total_amount = fields.Float(string="Ümumi Məbləğ", readonly=True, store=True)
    
    # Depozit məlumatları (Gənclik filialında depozit sistemi aktiv deyil)
    customer_deposit_balance = fields.Float(string="Müştəri Depoziti", related='partner_id.badminton_deposit_balance', readonly=True)
    deposit_used = fields.Float(string="İstifadə Edilən Depozit", default=0.0, help="Bu satışda istifadə edilən depozit məbləği")
    amount_paid = fields.Float(string="Ödənilən Məbləğ", default=0.0, help="Müştərinin faktiki ödədiyi məbləğ")
    amount_to_pay = fields.Float(string="Ödəniləcək Məbləğ", default=0.0, help="Depozit nəzərə alındıqdan sonra ödəniləcək məbləğ")
    deposit_added = fields.Float(string="Depozitə Əlavə", default=0.0, help="Artıq ödənişdən depozitə əlavə edilən məbləğ")
    
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
    
    @api.depends('sale_date', 'package_type')
    def _compute_expiry_date(self):
        for sale in self:
            if sale.sale_date:
                # Paketlərə görə son istifadə tarixini müəyyən et
                if sale.package_type in ['package_8', 'package_12'] or (sale.package_id and sale.package_id.package_type == 'monthly'):
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
            is_monthly = bool(sale.package_id and sale.package_id.package_type == 'monthly')
            sale.is_package = sale.package_type in ['package_8', 'package_12'] or is_monthly
    
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
        if not vals.get('name') or vals.get('name') == 'Yeni':
            vals['name'] = self.env['ir.sequence'].next_by_code('badminton.sale.genclik')
            
        sale = super(BadmintonSale, self).create(vals)
        
        # Əgər satış 'paid' vəziyyətində yaradılırsa, dərhal balansı artır və kassaya əlavə et
        if sale.state == 'paid':
            # Depozit əməliyyatlarını həyata keçir
            partner = sale.partner_id
            if sale.deposit_used > 0:
                # Depozitdən istifadə et
                partner.badminton_deposit_balance -= sale.deposit_used
            
            if sale.deposit_added > 0:
                # Artıq ödənişi depozitə əlavə et
                partner.badminton_deposit_balance += sale.deposit_added
            
            # Kassaya ödənilən məbləğin hamısını əlavə et
            if sale.amount_paid > 0:
                self.env['volan.cash.flow.genclik'].create({
                    'name': f"Badminton satışı: {sale.name}",
                    'date': fields.Date.today(),
                    'amount': sale.amount_paid,
                    'transaction_type': 'income',
                    'category': 'badminton_sale',
                    'partner_id': sale.partner_id.id,
                    'related_model': 'badminton.sale.genclik',
                    'related_id': sale.id,
                    'notes': f"{sale.hours_quantity} saat, Depozit: {sale.deposit_used} AZN, Ödəniş: {sale.amount_paid} AZN"
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
                
                # Depozit əməliyyatlarını həyata keçir
                partner = sale.partner_id
                if sale.deposit_used > 0:
                    # Depozitdən istifadə et
                    partner.badminton_deposit_balance -= sale.deposit_used
                
                if sale.deposit_added > 0:
                    # Artıq ödənişi depozitə əlavə et
                    partner.badminton_deposit_balance += sale.deposit_added
                
                # Kassaya ödənilən məbləğin hamısını əlavə et
                if sale.amount_paid > 0:
                    self.env['volan.cash.flow.genclik'].create({
                        'name': f"Badminton satışı: {sale.name}",
                        'date': fields.Date.today(),
                        'amount': sale.amount_paid,
                        'transaction_type': 'income',
                        'category': 'badminton_sale',
                        'partner_id': sale.partner_id.id,
                        'related_model': 'badminton.sale.genclik',
                        'related_id': sale.id,
                        'notes': f"{sale.hours_quantity} saat, Depozit: {sale.deposit_used} AZN, Ödəniş: {sale.amount_paid} AZN"
                    })
                
                # Müştəri hesabına saatları əlavə et
                sale._add_hours_to_customer()
                sale.credited_hours = sale.hours_quantity
    
    def action_cancel(self):
        """Satışı ləğv edir"""
        for sale in self:
            if sale.state in ['draft', 'confirmed']:
                sale.state = 'cancelled'
    
    def unlink(self):
        """Satış silinərkən əlaqəli kassa əməliyyatını da sil"""
        # Əvvəlcə kassa əməliyyatlarını tap və sil
        for sale in self:
            cash_flows = self.env['volan.cash.flow.genclik'].search([
                ('related_model', '=', 'badminton.sale.genclik'),
                ('related_id', '=', sale.id)
            ])
            if cash_flows:
                # related_model-i sıfırla ki, unlink qadağası işləməsin
                cash_flows.write({'related_model': False, 'related_id': False})
                cash_flows.unlink()
        
        return super(BadmintonSale, self).unlink()
    
    def _add_hours_to_customer(self):
        """Müştəri hesabına badminton saatlarını əlavə edir"""
        for sale in self:
            # Əgər artıq hesaba əlavə edilmişsə, təkrar etmə
            if sale.credited_hours > 0:
                return
                
            if sale.package_id and sale.package_id.package_type == 'monthly':
                sale._add_monthly_hours_to_customer()
                continue

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
                'description': f"Badminton saatları alışı: {sale.name}",
                'balance_channel': 'normal'
            })

    def _add_monthly_hours_to_customer(self):
        for sale in self:
            package = sale.package_id
            partner = sale.partner_id
            if not package:
                continue

            expiry_date = sale.sale_date + relativedelta(months=1) if sale.sale_date else fields.Date.today() + relativedelta(months=1)
            deduction_factor = 2.0 if package.is_gedis_package else 1.0

            line = self.env['badminton.monthly.balance.genclik'].create({
                'partner_id': partner.id,
                'sale_id': sale.id,
                'package_id': package.id,
                'initial_units': sale.hours_quantity,
                'remaining_units': sale.hours_quantity,
                'deduction_factor': deduction_factor,
                'is_gedis_package': package.is_gedis_package,
                'expiry_date': expiry_date,
            })

            self.env['badminton.balance.history.genclik'].create({
                'partner_id': partner.id,
                'sale_id': sale.id,
                'hours_added': sale.hours_quantity,
                'balance_before': 0.0,
                'balance_after': line.remaining_units,
                'transaction_type': 'purchase',
                'description': f"Aylıq paket alışı: {package.name}",
                'balance_channel': 'monthly',
                'monthly_line_id': line.id,
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
        ('adjustment', 'Düzəliş'),
        ('expiry', 'Müddət Bitdi')
    ], string="Əməliyyat Növü", required=True)

    hours_added = fields.Float(string="Alındı", default=0)
    hours_used = fields.Float(string="İstifadə", default=0)
    balance_before = fields.Float(string="Əvvəlki Balans")
    balance_after = fields.Float(string="Balans")
    
    description = fields.Text(string="Təsvir")
    transaction_date = fields.Datetime(string="Əməliyyat Tarixi", default=fields.Datetime.now)

    balance_channel = fields.Selection([
        ('normal', 'Normal Balans'),
        ('monthly', 'Aylıq Paket')
    ], string="Balans Mənbəyi", default='normal')
    monthly_line_id = fields.Many2one('badminton.monthly.balance.genclik', string="Aylıq Paket")
