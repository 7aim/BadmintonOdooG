# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BadmintonStockMovement(models.Model):
    _name = 'badminton.stock.movement.genclik'
    _description = 'Badminton Stok Hərəkəti'
    _order = 'movement_date desc, id desc'
    
    product_id = fields.Many2one('badminton.product.genclik', string="Məhsul", required=True, ondelete='cascade')
    movement_type = fields.Selection([
        ('in', 'Daxil Olma'),
        ('out', 'Çıxış'),
        ('adjustment', 'Düzəliş')
    ], string="Növ", required=True, default='in')
    quantity = fields.Integer(string="Miqdar", required=True)
    movement_date = fields.Date(string="Tarix", required=True, default=fields.Date.today)
    notes = fields.Text(string="Qeyd")
    reference = fields.Char(string="İstinad", help="Satış nömrəsi və ya digər istinad")
    
    # Hərəkətdən əvvəl və sonra balans
    balance_before = fields.Integer(string="Əvvəlki Stok", readonly=True)
    balance_after = fields.Integer(string="Sonrakı Stok", readonly=True)
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for movement in self:
            if movement.quantity <= 0:
                raise ValidationError("Miqdar 0-dan böyük olmalıdır!")
    
    @api.model
    def create(self, vals):
        # Əvvəlki balansı qeyd et
        product = self.env['badminton.product.genclik'].browse(vals['product_id'])
        vals['balance_before'] = product.stock_quantity
        
        # Stoku yenilə
        if vals['movement_type'] == 'in':
            product.stock_quantity += vals['quantity']
        elif vals['movement_type'] == 'out':
            if product.stock_quantity < vals['quantity']:
                raise ValidationError(
                    f"Kifayət qədər stok yoxdur! Mövcud: {product.stock_quantity}, Tələb: {vals['quantity']}"
                )
            product.stock_quantity -= vals['quantity']
        elif vals['movement_type'] == 'adjustment':
            # Düzəliş - mənfi də ola bilər
            product.stock_quantity = vals['quantity']
        
        vals['balance_after'] = product.stock_quantity
        
        return super(BadmintonStockMovement, self).create(vals)
