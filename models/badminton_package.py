# -*- coding: utf-8 -*-

from odoo import models, fields, api

class BadmintonPackage(models.Model):
    _name = 'badminton.package.genclik'
    _description = 'Badminton Paketləri - Gənclik'
    _order = 'name'

    name = fields.Char(string="Paket Adı", required=True)
    adult_price = fields.Float(string="Böyük Qiyməti", required=True)
    child_price = fields.Float(string="Kiçik Qiyməti", required=True)
    student_price = fields.Float(string="Tələbə Qiyməti", required=True)
    balance_count = fields.Integer(string="Badminton Balans Sayı", required=True, default=1)
    
    # Yeni sahələr
    discount_percent = fields.Float(string="Endirim Faizi (%)", default=0.0)
    package_type = fields.Selection([
        ('sale', 'Satış Paketi'),
        ('subscription', 'Abunəlik Paketi')
    ], string="Paket Növü", required=True, default='sale')
    
    active = fields.Boolean(string="Aktiv", default=True)