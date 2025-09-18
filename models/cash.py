from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class CashFlow(models.Model):
    _name = 'volan.cash.flow.genclik'
    _description = 'Kassa Axını'
    _order = 'date desc, id desc'
    
    name = fields.Char('Ad', required=True)
    date = fields.Date('Tarix', required=True, default=fields.Date.today)
    amount = fields.Float('Məbləğ', required=True)
    transaction_type = fields.Selection([
        ('income', 'Gəlir'),
        ('expense', 'Xərc'),
    ], string='Əməliyyat Növü', required=True)
    category = fields.Selection([
        ('badminton_sale', 'Badminton Satışı'),
        ('badminton_lesson', 'Badminton Dərs'),
        ('other', 'Digər'),
    ], string='Kateqoriya', required=True, default='other')
    notes = fields.Text('Qeydlər')
    partner_id = fields.Many2one('res.partner', string='Müştəri')
    related_model = fields.Char('Əlaqəli Model', readonly=True)
    related_id = fields.Integer('Əlaqəli ID', readonly=True)
    
    @api.constrains('amount', 'transaction_type')
    def _check_negative_balance(self):
        """Xərc əməliyyatı balansı mənfiyə düşürməməlidir"""
        for record in self:
            if record.transaction_type == 'expense':
                # Cari balansı hesablayırıq
                cash_balance = self.env['volan.cash.balance.genclik'].create({})
                if cash_balance.current_balance < record.amount:
                    raise ValidationError('Xəbərdarlıq: Yetərsiz balans! Bu xərc əməliyyatı balansı mənfiyə düşürəcək. '
                                          'Cari balans: {:.2f}, Xərc məbləği: {:.2f}'.format(
                                              cash_balance.current_balance, record.amount))
                    
    @api.model
    def create(self, vals):
        """Yazarkən xərc üçün balans yoxlaması"""
        # Əvvəlcə yaratmadan xərc və məbləğ kontrolunu yoxlayaq
        if vals.get('transaction_type') == 'expense':
            amount = vals.get('amount', 0)
            if amount > 0:  # Məbləğ müsbət olarsa (xərclər üçün normal)
                cash_balance = self.env['volan.cash.balance.genclik'].create({})
                if cash_balance.current_balance < amount:
                    raise ValidationError('Xəbərdarlıq: Yetərsiz balans! Bu xərc əməliyyatı balansı mənfiyə düşürəcək. '
                                          'Cari balans: {:.2f}, Xərc məbləği: {:.2f}'.format(
                                              cash_balance.current_balance, amount))
        return super(CashFlow, self).create(vals)

class CashBalance(models.TransientModel):
    _name = 'volan.cash.balance.genclik'
    _description = 'Kassa Balansı'

    # Tarix filtr sahələri
    date_filter = fields.Selection([
        ('all', 'Bütün Tarixlər'),
        ('today', 'Bu Gün'),
        ('week', 'Bu Həftə'),
        ('month', 'Bu Ay'),
        ('year', 'Bu İl'),
        ('custom', 'Özel Tarix')
    ], string='📅 Tarix Filtri', default='month', required=True)
    
    date_from = fields.Date('📅 Başlanğıc Tarix')
    date_to = fields.Date('📅 Bitmə Tarix')

    # Gəlir növləri
    badminton_sales_income = fields.Float('🏸 Badminton Satışları', readonly=True)
    badminton_lessons_income = fields.Float('📚 Badminton Dərs Abunəlikləri', readonly=True)
    other_income = fields.Float('💰 Digər Gəlirlər', readonly=True)
    
    # Xərclər
    total_expenses = fields.Float('📉 Ümumi Xərclər', readonly=True)
    
    # Ümumi məlumatlar
    total_income = fields.Float('📈 Ümumi Gəlir', readonly=True)
    current_balance = fields.Float('💵 Cari Balans', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # İlkin yükləmədə cari ay filtri ilə hesabla
        self._calculate_balance_data(res)
        return res

    def _get_date_domain(self):
        """Tarix filtrinə əsasən domain qaytarır"""
        today = fields.Date.today()
        
        if self.date_filter == 'all':
            return []
        elif self.date_filter == 'today':
            return [('date', '=', today)]
        elif self.date_filter == 'week':
            # Həftənin ilk və son gününü hesabla (Bazar ertəsi - Bazar)
            weekday = today.weekday()
            date_from = today - timedelta(days=weekday)
            date_to = date_from + timedelta(days=6)
            return [('date', '>=', date_from), ('date', '<=', date_to)]
        elif self.date_filter == 'month':
            # Ayın ilk və son günlərini hesabla
            date_from = today.replace(day=1)
            if today.month == 12:
                date_to = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
            else:
                date_to = today.replace(month=today.month+1, day=1) - timedelta(days=1)
            return [('date', '>=', date_from), ('date', '<=', date_to)]
        elif self.date_filter == 'year':
            # İlin ilk və son günlərini hesabla
            date_from = today.replace(month=1, day=1)
            date_to = today.replace(month=12, day=31)
            return [('date', '>=', date_from), ('date', '<=', date_to)]
        elif self.date_filter == 'custom' and self.date_from and self.date_to:
            return [('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        return []

    def _calculate_balance_data(self, res=None):
        """Balans məlumatlarını tarix filtrinə əsasən hesablayır"""
        if res is None:
            res = {}
            
        cash_flow_obj = self.env['volan.cash.flow.genclik']
        date_domain = self._get_date_domain()
        
        # Badminton satış gəlirləri
        badminton_sales_domain = [
            ('transaction_type', '=', 'income'),
            ('category', '=', 'badminton_sale')
        ] + date_domain
        badminton_sales_income = sum(cash_flow_obj.search(badminton_sales_domain).mapped('amount'))
        
        # Badminton dərs gəlirləri
        badminton_lessons_domain = [
            ('transaction_type', '=', 'income'),
            ('category', '=', 'badminton_lesson')
        ] + date_domain
        badminton_lessons_income = sum(cash_flow_obj.search(badminton_lessons_domain).mapped('amount'))
        
        # Digər gəlirlər
        other_income_domain = [
            ('transaction_type', '=', 'income'),
            ('category', '=', 'other')
        ] + date_domain
        other_income = sum(cash_flow_obj.search(other_income_domain).mapped('amount'))
        
        # Ümumi gəlir
        total_income = badminton_sales_income + badminton_lessons_income + other_income
        
        # Ümumi xərclər - sadə şəkildə bütün xərcləri hesablayırıq
        expense_domain = [
            ('transaction_type', '=', 'expense')
        ] + date_domain
        total_expenses = sum(cash_flow_obj.search(expense_domain).mapped('amount'))
        
        # Cari balans = Ümumi gəlir - Ümumi xərc
        current_balance = total_income - total_expenses
        
        res.update({
            'badminton_sales_income': badminton_sales_income,
            'badminton_lessons_income': badminton_lessons_income,
            'other_income': other_income,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'current_balance': current_balance,
        })
        
        return res

    def action_refresh(self):
        """Balansı yenilə düyməsi"""
        values = {}
        self._calculate_balance_data(values)
        self.write(values)
        # Sadəcə True qaytarmaq formu yenilənməyə məcbur edir
        return True
        
    @api.model
    def create_income_transaction(self, values):
        """
        Kassa axınında yeni gəlir əməliyyatı yaradır
        Xarici modellərin cash.flow yaratması üçün istifadə olunur
        """
        cash_flow_obj = self.env['volan.cash.flow.genclik']
        values['transaction_type'] = 'income'
        return cash_flow_obj.create(values)
        
    @api.model
    def create_expense_transaction(self, values):
        """
        Kassa axınında yeni xərc əməliyyatı yaradır
        Xarici modellərin cash.flow yaratması üçün istifadə olunur
        """
        cash_flow_obj = self.env['volan.cash.flow.genclik']
        values['transaction_type'] = 'expense'
        
        # Xərc əməliyyatı yaratmadan əvvəl balansı yoxlayırıq
        if values.get('amount', 0) > 0:
            # Cari balansı hesablayırıq
            current_balance = self._calculate_current_balance()
            if current_balance < values.get('amount', 0):
                raise ValidationError('Xəbərdarlıq: Yetərsiz balans! Bu xərc əməliyyatı balansı mənfiyə düşürəcək. '
                                      'Cari balans: {:.2f}, Xərc məbləği: {:.2f}'.format(
                                          current_balance, values.get('amount', 0)))
        
        return cash_flow_obj.create(values)
        
    def _calculate_current_balance(self):
        """Cari balansı hesablayır"""
        cash_flow_obj = self.env['volan.cash.flow.genclik']
        
        # Gəlirlər
        income = sum(cash_flow_obj.search([('transaction_type', '=', 'income')]).mapped('amount'))
        
        # Xərclər
        expenses = sum(cash_flow_obj.search([('transaction_type', '=', 'expense')]).mapped('amount'))
        
        return income - expenses
        
    def generate_cash_report(self):
        """Nağd pul hesabat səhifəsini açır"""
        self.ensure_one()
        domain = self._get_date_domain()
        action = {
            'name': 'Kassa Hesabatı',
            'type': 'ir.actions.act_window',
            'res_model': 'volan.cash.flow.genclik',
            'view_mode': 'pivot,graph,list,form',
            'domain': domain,  # Bütün əməliyyatları göstər (həm gəlir, həm xərc)
            'context': {
                'pivot_measures': ['amount'],
                'search_default_group_by_transaction_type': 1,  # Əməliyyat növünə görə qruplaşdır
                'search_default_group_by_category': 1,
                'search_default_group_by_date': 1
            }
        }
        return action
        
    def _open_cash_flow_view(self, title, domain):
        """Filtrələnmiş kassa əməliyyatı siyahısını göstərir"""
        self.ensure_one()
        action = {
            'name': title,
            'type': 'ir.actions.act_window',
            'res_model': 'volan.cash.flow.genclik',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {'create': False}
        }
        return action
        
    def show_badminton_sales(self):
        """Badminton satışlarını göstərir"""
        self.ensure_one()
        domain = self._get_date_domain() + [
            ('category', '=', 'badminton_sale'),
            ('transaction_type', '=', 'income')
        ]
        return self._open_cash_flow_view('Badminton Satışları', domain)
        
    def show_badminton_lessons(self):
        """Badminton dərs gəlirlərini göstərir"""
        self.ensure_one()
        domain = self._get_date_domain() + [
            ('category', '=', 'badminton_lesson'),
            ('transaction_type', '=', 'income')
        ]
        return self._open_cash_flow_view('Badminton Dərs Gəlirləri', domain)
        
    def show_other_income(self):
        """Digər gəlirləri göstərir"""
        self.ensure_one()
        domain = self._get_date_domain() + [
            ('category', '=', 'other'),
            ('transaction_type', '=', 'income')
        ]
        return self._open_cash_flow_view('Digər Gəlirlər', domain)
        
    def show_expenses(self):
        """Xərcləri göstərir"""
        self.ensure_one()
        domain = self._get_date_domain() + [
            ('transaction_type', '=', 'expense')
        ]
        return self._open_cash_flow_view('Xərclər', domain)

    @api.onchange('date_filter', 'date_from', 'date_to')
    def _onchange_date_filter(self):
        """Tarix filtri dəyişəndə balansı yenilə"""
        values = {}
        self._calculate_balance_data(values)
        for field, value in values.items():
            setattr(self, field, value)