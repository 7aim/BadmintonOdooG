# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class BadmintonStockUpdateWizard(models.TransientModel):
    _name = 'badminton.stock.update.wizard.genclik'
    _description = 'Stok Yeniləmə Sihirbazı'
    
    product_id = fields.Many2one('badminton.product.genclik', string="Məhsul", required=True)
    movement_type = fields.Selection([
        ('in', 'Daxil Olma'),
        ('out', 'Çıxış'),
    ], string="Əməliyyat Növü", required=True, default='in')
    quantity = fields.Integer(string="Miqdar", required=True, default=1)
    movement_date = fields.Date(string="Tarix", required=True, default=fields.Date.today)
    notes = fields.Text(string="Qeyd")
    
    current_stock = fields.Integer(string="Cari Stok", related='product_id.stock_quantity', readonly=True)
    
    @api.constrains('quantity')
    def _check_quantity(self):
        for wizard in self:
            if wizard.quantity <= 0:
                raise ValidationError("Miqdar 0-dan böyük olmalıdır!")
    
    def action_update_stock(self):
        """Stoku yenilə və hərəkət yarat"""
        self.ensure_one()
        
        # Stok hərəkəti yarat
        self.env['badminton.stock.movement.genclik'].create({
            'product_id': self.product_id.id,
            'movement_type': self.movement_type,
            'quantity': self.quantity,
            'movement_date': self.movement_date,
            'notes': self.notes,
            'reference': 'Manual Update'
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurlu!',
                'message': f'Stok yeniləndi. Yeni balans: {self.product_id.stock_quantity}',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }   
        }
