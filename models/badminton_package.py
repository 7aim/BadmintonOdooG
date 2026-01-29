# -*- coding: utf-8 -*-

from odoo import models, fields, api

class BadmintonPackage(models.Model):
    _name = 'badminton.package.genclik'
    _description = 'Badminton Paketləri'
    _order = 'name'

    name = fields.Char(string="Paket Adı", required=True)
    adult_price = fields.Float(string="Qiymət", required=True, help="Böyük Qiyməti")
    child_price = fields.Float(string="Kiçik Qiyməti", required=True)
    balance_count = fields.Integer(string="Badminton Balans Sayı", required=True, default=1)
    
    # Yeni sahələr
    discount_percent = fields.Float(string="Endirim Faizi (%)", default=0.0)
    package_type = fields.Selection([
        ('sale', 'Satış Paketi'),
        #('subscription', 'Dərs Paketi'),
        ('monthly', 'Abunəlik Paketlər')
    ], string="Paket Növü", required=True, default='sale')
    is_gedis_package = fields.Boolean(string="Gediş Paketi",
                                      help="Bu aylıq paket üçün hər sessiya 2 balans sərf edir")
    
    active = fields.Boolean(string="Aktiv", default=True)