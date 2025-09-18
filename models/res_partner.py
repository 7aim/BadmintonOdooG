# -*- coding: utf-8 -*-
from odoo import models, fields, api
import qrcode
import base64
import io

class VolanPartner(models.Model):
    _inherit = 'res.partner'

    # 1. Doğum Tarixi Sahəsi
    birth_date = fields.Date(string="Doğum Tarixi")

    age = fields.Integer(string="Yaş", compute='_compute_age', store=False)

    # 2. Filial Sahəsi
    branch = fields.Selection([
        ('genclik', 'Gənclik'),
        ('yasamal', 'Yasamal')
    ], string="Filial", required=True)
    
    # 3. Müştəri Mənbəyi
    customer_source = fields.Selection([
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('friends', 'Dost və Tanışlar'),
        ('outdoor', 'Küçə Reklamı'),
        ('other', 'Digər')
    ], string="Müştəri Mənbəyi")
    
    # 4. Əlavə Məlumatlar Sahəsi
    additional_info = fields.Text(string="Əlavə Məlumatlar")

    # 3. QR Kod Şəkli Sahəsi (Hesablanan)
    qr_code_image = fields.Binary(string="QR Kod", compute='_compute_qr_code', store=True)

    # 4. Badminton Balans Sahəsi
    badminton_balance = fields.Integer(string="Badminton Balansı (saat)", default=0, 
                                      help="Müştərinin qalan badminton saatlarının sayı")
    
    # 5. Badminton Satış Tarixçəsi
    badminton_sale_ids = fields.One2many('badminton.sale.genclik', 'partner_id', string="Badminton Satışları")
    badminton_balance_history_ids = fields.One2many('badminton.balance.history.genclik', 'partner_id', string="Balans Tarixçəsi")

    # 7. Məşqçi bayrağı
    is_coach = fields.Boolean(string="Məşqçidir", default=False, help="İşçinin məşqçi olub olmadığını göstərir")

    @api.depends('birth_date')
    def _compute_age(self):
        """Müştərinin doğum tarixindən yaşını hesablayır"""
        today = fields.Date.today()
        for partner in self:
            if partner.birth_date:
                birth_date = partner.birth_date
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                partner.age = age
            else:
                partner.age = 0

    @api.depends('name', 'write_date')
    def _compute_qr_code(self):
        """Her müşteri üçün unikal ID və adına əsaslanan bir QR kod yaradır."""
        for partner in self:
            if partner.id and partner.name:
                # ID + Ad kombinasiyası ilə daha unikal QR kod
                qr_payload = f"ID-{partner.id}-NAME-{partner.name}"
                try:
                    img = qrcode.make(qr_payload)
                    temp = io.BytesIO()
                    img.save(temp, format="PNG")
                    qr_image = base64.b64encode(temp.getvalue())
                    partner.qr_code_image = qr_image
                except Exception:
                    partner.qr_code_image = False
            else:
                partner.qr_code_image = False




    """@api.model
    def _auto_init(self):
        res = super(VolanPartner, self)._auto_init()
        
        # Check if badminton_balance column exists, if not add it
        try:
            self.env.cr.execute("SELECT badminton_balance FROM res_partner LIMIT 1")
        except Exception:
            # Column doesn't exist, create it
            self.env.cr.execute("ALTER TABLE res_partner ADD COLUMN badminton_balance INTEGER DEFAULT 0")
            self.env.cr.execute("UPDATE res_partner SET badminton_balance = 0 WHERE badminton_balance IS NULL")
            self.env.cr.commit()
        
        return res"""