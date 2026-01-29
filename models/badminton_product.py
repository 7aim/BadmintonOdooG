# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BadmintonProduct(models.Model):
    _name = 'badminton.product.genclik'
    _description = 'Badminton Raketləri'
    _order = 'name'
    
    name = fields.Char(string="Raket Adı", required=True, tracking=True)
    image = fields.Binary(string="Şəkil", attachment=True)
    price = fields.Float(string="Qiymət (AZN)", required=True, digits=(10, 2), tracking=True)
    model = fields.Selection([
        ('model1', 'Model 1'),
        ('model2', 'Model 2'),
    ], string="Model", default='model2', tracking=True)

    # Stok
    stock_quantity = fields.Integer(string="Stok Sayı", default=0, tracking=True, help="Mövcud stok sayı")
    stock_movement_ids = fields.One2many('badminton.stock.movement.genclik', 'product_id', string="Stok Hərəkətləri")
    
    # Əlavə məlumatlar
    description = fields.Text(string="Təsvir")
    active = fields.Boolean(string="Aktiv", default=True)
    currency_id = fields.Many2one('res.currency', string="Valyuta", default=lambda self: self.env.company.currency_id)
    
    # Statistika
    sale_count = fields.Integer(string="Satış Sayı", compute='_compute_sale_count', store=True)
    total_revenue = fields.Float(string="Ümumi Gəlir (AZN)", compute='_compute_total_revenue', store=True, digits=(10, 2))
    
    @api.depends('sale_line_ids')
    def _compute_sale_count(self):
        for product in self:
            product.sale_count = len(product.sale_line_ids)
    
    @api.depends('sale_line_ids.total_price')
    def _compute_total_revenue(self):
        for product in self:
            product.total_revenue = sum(product.sale_line_ids.mapped('total_price'))
    
    sale_line_ids = fields.One2many('badminton.product.sale.line.genclik', 'product_id', string="Satışlar")
    
    @api.constrains('price')
    def _check_price(self):
        for product in self:
            if product.price < 0:
                raise ValidationError("Qiymət mənfi ola bilməz!")
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('price', 0) < 0:
                raise ValidationError("Qiymət mənfi ola bilməz!")
        return super(BadmintonProduct, self).create(vals_list)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Bu adda raket artıq mövcuddur!')
    ]
