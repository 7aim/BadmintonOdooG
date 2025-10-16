# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta

class BadmintonSessionFilter(models.TransientModel):
    _name = 'badminton.session.filter.genclik'
    _description = 'Badminton Sessiyaları Filtri'

    # Tarix filtri sahələri
    date_filter = fields.Selection([
        ('all', 'Bütün Tarixlər'),
        ('today', 'Bu Gün'),
        ('week', 'Bu Həftə'),
        ('month', 'Bu Ay'),
        ('year', 'Bu İl'),
        ('custom', 'Xüsusi Tarix')
    ], string='📅 Tarix Filtri', default='month', required=True)
    
    date_from = fields.Date('📅 Başlanğıc Tarix')
    date_to = fields.Date('📅 Bitmə Tarix')
    
    def _get_date_domain(self):
        """Tarix filtrinə əsasən domain qaytarır"""
        today = fields.Date.today()
        
        if self.date_filter == 'all':
            return []
        elif self.date_filter == 'today':
            return [('start_time', '>=', datetime.combine(today, datetime.min.time())),
                    ('start_time', '<=', datetime.combine(today, datetime.max.time()))]
        elif self.date_filter == 'week':
            # Həftənin ilk və son gününü hesabla (Bazar ertəsi - Bazar)
            weekday = today.weekday()
            date_from = today - timedelta(days=weekday)
            date_to = date_from + timedelta(days=6)
            return [('start_time', '>=', datetime.combine(date_from, datetime.min.time())),
                    ('start_time', '<=', datetime.combine(date_to, datetime.max.time()))]
        elif self.date_filter == 'month':
            # Ayın ilk və son günlərini hesabla
            date_from = today.replace(day=1)
            if today.month == 12:
                date_to = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
            else:
                date_to = today.replace(month=today.month+1, day=1) - timedelta(days=1)
            return [('start_time', '>=', datetime.combine(date_from, datetime.min.time())),
                    ('start_time', '<=', datetime.combine(date_to, datetime.max.time()))]
        elif self.date_filter == 'year':
            # İlin ilk və son günlərini hesabla
            date_from = today.replace(month=1, day=1)
            date_to = today.replace(month=12, day=31)
            return [('start_time', '>=', datetime.combine(date_from, datetime.min.time())),
                    ('start_time', '<=', datetime.combine(date_to, datetime.max.time()))]
        elif self.date_filter == 'custom' and self.date_from and self.date_to:
            return [('start_time', '>=', datetime.combine(self.date_from, datetime.min.time())),
                    ('start_time', '<=', datetime.combine(self.date_to, datetime.max.time()))]
        return []
        
    def action_apply_filter(self):
        domain = self._get_date_domain()
        
        return {
            'name': 'Filtrlənmiş Sessiyalar',
            'type': 'ir.actions.act_window',
            'res_model': 'badminton.session.genclik',
            'view_mode': 'list,form',
            'domain': domain,
        }
