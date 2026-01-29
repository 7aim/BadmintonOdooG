# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BadmintonProductSale(models.Model):
    _name = 'badminton.product.sale.genclik'
    _description = 'Badminton Raketka Satışı'
    _order = 'sale_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string="Satış Nömrəsi", readonly=True, default="Yeni", tracking=True)
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True, tracking=True)
    sale_date = fields.Datetime(string="Satış Tarixi", required=True, default=fields.Datetime.now, tracking=True)
    currency_id = fields.Many2one('res.currency', string="Valyuta", default=lambda self: self.env.company.currency_id)

    payment_method = fields.Selection([
        ('cash', 'Nağd'),
        ('card', 'Kartdan karta'),
    ], string="Ödəniş Metodu", default='cash', tracking=True)

    # Satış xətləri
    sale_line_ids = fields.One2many('badminton.product.sale.line.genclik', 'sale_id', string="Raketka")
    
    # Ümumi məbləğ
    total_amount = fields.Float(string="Ümumi Məbləğ (AZN)", compute='_compute_total_amount', 
                                store=True, digits=(10, 2), tracking=True)
    
    # Vəziyyət
    state = fields.Selection([
        ('draft', 'Təsdiqlənməyib'),
        ('confirmed', 'Təsdiqlənib'),
        ('cancelled', 'Ləğv Edilib')
    ], default='draft', string="Vəziyyət", tracking=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.model
    def create(self, vals):
        if vals.get('total_amount', 0) <= 0:
            raise ValidationError("Ümumi məbləğ 0-dan böyük olmalıdır!")
        if vals.get('name', 'Yeni') == 'Yeni':
            vals['name'] = self.env['ir.sequence'].next_by_code('badminton.product.sale') or 'BPS001'
        return super(BadmintonProductSale, self).create(vals)

    @api.model
    def create(self, vals):
        # Qrup kodu: S-1, S-2, S-3... formatında (sıralama ilə)
        group_count = self.search_count([])
        next_number = group_count + 1    
        vals['name'] = f"S-{next_number}"
        return super(BadmintonProductSale, self).create(vals)
    @api.depends('sale_line_ids.total_price')
    def _compute_total_amount(self):
        for sale in self:
            sale.total_amount = sum(sale.sale_line_ids.mapped('total_price'))
    
    def action_confirm(self):
        """Satışı təsdiqlə və stokdan azalt"""
        for sale in self:
            if not sale.sale_line_ids:
                raise ValidationError("Ən azı bir raketka əlavə etməlisiniz!")
            
            # Stokdan azalt və hərəkət yarat
            for line in sale.sale_line_ids:
                if line.product_id.stock_quantity < line.quantity:
                    raise ValidationError(
                        f"'{line.product_id.name}' məhsulu üçün kifayət qədər stok yoxdur! "
                        f"Mövcud: {line.product_id.stock_quantity}, Tələb: {line.quantity}"
                    )
                
                # Stok hərəkəti yarat
                self.env['badminton.stock.movement.genclik'].create({
                    'product_id': line.product_id.id,
                    'movement_type': 'out',
                    'quantity': line.quantity,
                    'movement_date': sale.sale_date.date() if sale.sale_date else fields.Date.today(),
                    'reference': sale.name,
                    'notes': f"Satış: {sale.partner_id.name}"
                })
            
            sale.state = 'confirmed'
    
    def action_cancel(self):
        """Satışı ləğv et və stoku geri qaytar"""
        for sale in self:
            # Əgər əvvəlcə təsdiqlənibsə, stoku geri qaytar
            if sale.state == 'confirmed':
                for line in sale.sale_line_ids:
                    line.product_id.stock_quantity += line.quantity
            
            sale.state = 'cancelled'
    
    def action_draft(self):
        """Təsdiqlənməyib vəziyyətinə qaytar"""
        for sale in self:
            sale.state = 'draft'


class BadmintonProductSaleLine(models.Model):
    _name = 'badminton.product.sale.line.genclik'
    _description = 'Badminton Raketka Satış Xətti'
    
    sale_id = fields.Many2one('badminton.product.sale.genclik', string="Satış", required=True, ondelete='cascade')
    product_id = fields.Many2one('badminton.product.genclik', string="Raketka", required=True)
    
    # Qiymət məlumatları
    quantity = fields.Integer(string="Miqdar", required=True, default=1)
    unit_price = fields.Float(string="Vahid Qiyməti (AZN)", required=True, digits=(10, 2))
    total_price = fields.Float(string="Ümumi Qiymət (AZN)", compute='_compute_total_price', 
                               store=True, digits=(10, 2))
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    
    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Raketka seçildikdə avtomatik qiyməti doldur"""
        if self.product_id:
            self.unit_price = self.product_id.price
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError("Miqdar 0-dan böyük olmalıdır!")
    
    @api.constrains('unit_price')
    def _check_unit_price(self):
        for line in self:
            if line.unit_price < 0:
                raise ValidationError("Qiymət mənfi ola bilməz!")