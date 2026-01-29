# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class BadmintonSaleNameMigration(models.TransientModel):
    _name = 'badminton.sale.name.migration.genclik'
    _description = 'Badminton Satış Nömrələrini Yenilə'

    sale_count = fields.Integer(string="Yenilənəcək Satış Sayı", readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        res = super(BadmintonSaleNameMigration, self).default_get(fields_list)
        # Dublikat və ya köhnə formatdakı satışları say
        sales = self.env['badminton.sale.genclik'].search([])
        duplicate_count = 0
        seen_names = set()
        for sale in sales:
            if sale.name in seen_names or not sale.name or sale.name == 'Yeni':
                duplicate_count += 1
            seen_names.add(sale.name)
        res['sale_count'] = duplicate_count
        return res

    def action_migrate_sale_names(self):
        """Bütün badminton satışlarının adlarını unikal sequence ilə yenilə"""
        self.ensure_one()
        
        BadmintonSale = self.env['badminton.sale.genclik']
        sales = BadmintonSale.search([('name', '!=', False)], order='create_date asc, id asc')
        
        _logger.info(f"Badminton satış adlarını yeniləyir: {len(sales)} satış")
        
        # Köhnə adları saxla
        old_names = {}
        for sale in sales:
            old_names[sale.id] = sale.name
        
        # SQL constraint-i müvəqqəti söndür
        self.env.cr.execute("""
            ALTER TABLE badminton_sale_genclik DROP CONSTRAINT IF EXISTS badminton_sale_genclik_name_unique;
        """)
        
        updated_count = 0
        error_count = 0
        
        for sale in sales:
            try:
                # Yeni unikal ad yarat
                new_name = self.env['ir.sequence'].next_by_code('badminton.sale.genclik')
                if not new_name:
                    new_name = f"S-{sale.id:05d}"
                
                # SQL ilə birbaşa yenilə (ORM-i bypass et)
                self.env.cr.execute("""
                    UPDATE badminton_sale_genclik 
                    SET name = %s 
                    WHERE id = %s
                """, (new_name, sale.id))
                
                updated_count += 1
                _logger.info(f"Satış ID {sale.id}: {old_names[sale.id]} → {new_name}")
                
            except Exception as e:
                error_count += 1
                _logger.error(f"Satış ID {sale.id} yenilənərkən xəta: {str(e)}")
        
        # SQL constraint-i yenidən əlavə et
        self.env.cr.execute("""
            ALTER TABLE badminton_sale_genclik 
            ADD CONSTRAINT badminton_sale_genclik_name_unique UNIQUE(name);
        """)
        
        self.env.cr.commit()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurla Tamamlandı',
                'message': f'{updated_count} satış uğurla yeniləndi. {error_count} xəta.',
                'type': 'success',
                'sticky': False,
            }
        }
