from odoo import models, fields, api
from odoo.osv.expression import OR
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class CashFlow(models.Model):
    _name = 'volan.cash.flow.genclik'
    _description = 'Kassa Axını'
    _order = 'date desc, id desc'
    
    name = fields.Char('Ad', required=True)
    date = fields.Date('Tarix', required=True, default=fields.Date.today)
    amount = fields.Float('Məbləğ', required=True)
    transaction_type = fields.Selection([
        ('income', 'Mədaxil'),
        ('expense', 'Məxaric'),
    ], string='Əməliyyat Növü', required=True)
    category = fields.Selection([
        ('badminton_sale', 'Badminton Satışı'),
        ('badminton_lesson', 'Badminton Dərs'),
        ('basketball_lesson', 'Basketbol Dərs'),
        ('other', 'Digər'),
    ], string='Kateqoriya', required=True, default='other')
    
    # Sport növü əlavə edək
    sport_type = fields.Selection([
        ('badminton', 'Badminton'),
        ('basketball', 'Basketbol'),
        ('general', 'Ümumi')
    ], string='İdman Növü', required=True, default='general', help='Bu əməliyyatın hansı idman növünə aid olduğunu göstərir')
    notes = fields.Text('Qeydlər')
    partner_id = fields.Many2one('res.partner', string='Müştəri')
    related_model = fields.Char('Əlaqəli Model', readonly=True)
    related_id = fields.Integer('Əlaqəli ID', readonly=True)
    has_source = fields.Boolean('Mənbə Sənəd Var', compute='_compute_has_source', store=False)
    
    @api.depends('related_model', 'related_id')
    def _compute_has_source(self):
        """Mənbə sənədin olub-olmadığını yoxla"""
        for record in self:
            record.has_source = bool(record.related_model and record.related_id)
    
    def action_view_source(self):
        """Mənbə sənədə keçid et"""
        self.ensure_one()
        if not self.related_model or not self.related_id:
            raise ValidationError('Bu kassa əməliyyatının mənbə sənədi yoxdur!')
        
        # Model adını tap
        try:
            model_obj = self.env[self.related_model].browse(self.related_id)
            if not model_obj.exists():
                raise ValidationError('Mənbə sənəd tapılmadı! Ola bilsin silinib.')
        except Exception:
            raise ValidationError(f'Model "{self.related_model}" tapılmadı!')
        
        # Əgər payment modelidirsə, əsas lesson-a keçid et
        target_model = self.related_model
        target_id = self.related_id
        
        if 'payment' in self.related_model.lower():
            # Ödəniş modelindən əsas dərs abunəliyinə keçid
            if hasattr(model_obj, 'lesson_id') and model_obj.lesson_id:
                target_model = model_obj.lesson_id._name
                target_id = model_obj.lesson_id.id
        
        # View-ə keçid
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mənbə Əməliyyat',
            'res_model': target_model,
            'res_id': target_id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def unlink(self):
        """Mənbə sənədi olan kassa əməliyyatını silməyə icazə vermə"""
        for record in self:
            if record.related_model and record.related_id:
                raise ValidationError(
                    f'⛔ Bu kassa əməliyyatı "{record.name}" bir sənəd tərəfindən yaradılıb!\n\n'
                    f'Silmək üçün əsas sənədi silməlisiniz.\n'
                )
        return super(CashFlow, self).unlink()
    
    #@api.constrains('amount', 'transaction_type')
    #def _check_negative_balance(self):
    #    """Xərc əməliyyatı balansı mənfiyə düşürməməlidir"""
    #    for record in self:
    #        if record.transaction_type == 'expense':
    #            # Cari balansı hesablayırıq
    #            cash_balance = self.env['volan.cash.balance'].create({})
    #            if cash_balance.current_balance < record.amount:
    #                raise ValidationError('Xəbərdarlıq: Yetərsiz balans! Bu xərc əməliyyatı balansı mənfiyə düşürəcək. '
    #                                      'Cari balans: {:.2f}, Xərc məbləği: {:.2f}'.format(
    #                                              cash_balance.current_balance, record.amount))

    @api.model
    def create(self, vals):
        """Yazarkən xərc üçün balans yoxlaması"""
        # Əvvəlcə yaratmadan xərc və məbləğ kontrolunu yoxlayaq
        if vals.get('transaction_type') == 'expense':
            amount = vals.get('amount', 0)
            sport_type = vals.get('sport_type', 'general')
            #if amount > 0:  # Məbləğ müsbət olarsa (xərclər üçün normal)
            #    current_balance = self._get_current_balance_by_sport(sport_type)
            #    if current_balance < amount:
            #        raise ValidationError('Xəbərdarlıq: Yetərsiz balans! Bu xərc əməliyyatı balansı mənfiyə düşürəcək. '
            #                              'Cari balans: {:.2f}, Xərc məbləği: {:.2f}'.format(
            #                                  current_balance, amount))
        return super(CashFlow, self).create(vals)

class BadmintonCashBalance(models.TransientModel):
    _name = 'badminton.cash.balance.genclik'
    _description = 'Badminton Kassa Balansı'

    date_filter = fields.Selection([
        #('all', 'Bütün Tarixlər'),
        #('today', 'Bu Gün'),
        #('week', 'Bu Həftə'),
        #('month', 'Bu Ay'),
        #('year', 'Bu İl'),
        ('custom', 'Özel Tarix')
    ], string='📅 Tarix Filtri', default='custom', required=True)

    date_from = fields.Date('📅 Başlanğıc Tarix', default=fields.Date.today)
    date_to = fields.Date('📅 Bitmə Tarix', default=fields.Date.today)

    subscription_cash_amount = fields.Float('💵 Abunəlik Nağd', readonly=True)
    subscription_card_amount = fields.Float('💳 Abunəlik Kart', readonly=True)
    subscription_total_amount = fields.Float('💰 Abunəlik Ümumi', readonly=True)

    badminton_sale_cash_amount = fields.Float('💵 Badminton Satışı Nağd', readonly=True)
    badminton_sale_card_amount = fields.Float('💳 Badminton Satışı Kart', readonly=True)
    badminton_sale_abonent_amount = fields.Float('🎫 Badminton Satışı Abunəçi', readonly=True)
    badminton_sale_total_amount = fields.Float('💰 Badminton Satışı Ümumi', readonly=True)

    other_income_amount = fields.Float('💼 Mədaxil', readonly=True)
    other_expense_amount = fields.Float('📉 Məxaric', readonly=True)
    other_net_amount = fields.Float('🧾 Net Nəticə', readonly=True)

    overall_cash_income = fields.Float('💵 Nağd Qalıq', readonly=True)
    overall_card_income = fields.Float('💳 Kart Qalıq', readonly=True)
    overall_total_income = fields.Float('💰 Ümumi Qalıq', readonly=True)
    
    cashbox_balance = fields.Float('🏦 Son Qalıq', readonly=True,
                                   help='Bütün tarixlər üzrə Ümumi Qalıq')
    initial_balance = fields.Float('🧾 İlkin Qalıq', readonly=True,
                                   help='Kassa Balansı - seçilmiş tarix aralığındakı Ümumi Qalıq')

    total_children_count = fields.Integer('👥 Ümumi Müştəri', readonly=True)
    new_children_count = fields.Integer('🆕 Yeni Müştəri', readonly=True)

    delayed_payments_amount = fields.Float('⏰ Gecikmiş Ödənişlər', readonly=True,
                                          help="Real_date bu tarix aralığında olan amma payment_date başqa tarixdə olan ödənişlər")

    # Gecikməyən ödənişlər (məlumat xarakterli)
    ontime_payments_amount = fields.Float('✅ Aylıq net nəticə', readonly=True, compute='_compute_ontime_payments',
                                         help="Abunəlik Ümumi - Gecikmiş Ödənişlər")

    cash_entries = fields.Integer('💵 Nağd Girişlər', readonly=True)
    card_entries = fields.Integer('💳 Card to Card Girişlər', readonly=True)
    abonent_entries = fields.Integer('🎫 Abunəçi Girişlər', readonly=True)
    onefit_entries = fields.Integer('🏃 1FIT Girişlər', readonly=True)
    push30_entries = fields.Integer('⚡ PUSH30 Girişlər', readonly=True)
    push30_plus_entries = fields.Integer('🔥 PUSH30+ Girişlər', readonly=True)
    tripsome_entries = fields.Integer('🚗 Tripsome Girişlər', readonly=True)
    total_entries = fields.Integer('📊 Ümumi Giriş Sayı', readonly=True)

    cash_payments = fields.Float('💵 Nağd Ödənişlər', readonly=True)
    card_payments = fields.Float('💳 Card to Card Ödənişlər', readonly=True)
    abonent_payments = fields.Float('🎫 Abunəçi Ödənişləri', readonly=True)
    total_payments = fields.Float('💰 Ümumi Ödənişlər', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        metrics = self._gather_metrics(override=res)
        res.update(metrics)
        return res

    @api.depends('subscription_total_amount', 'delayed_payments_amount')
    def _compute_ontime_payments(self):
        """Gecikməyən ödənişləri hesabla: Abunəlik Ümumi - Gecikmiş Ödənişlər"""
        for record in self:
            record.ontime_payments_amount = record.subscription_total_amount - record.delayed_payments_amount


    def _resolve_filter_state(self, override=None):
        if override:
            date_filter = override.get('date_filter') or 'custom'
            date_from = override.get('date_from')
            date_to = override.get('date_to')
        else:
            date_filter = self.date_filter or 'custom'
            date_from = self.date_from
            date_to = self.date_to
        return {
            'date_filter': date_filter,
            'date_from': date_from,
            'date_to': date_to,
        }

    def _get_date_range(self, state):
        today = fields.Date.today()
        date_filter = state['date_filter']

        if date_filter == 'all':
            return (False, False)
        if date_filter == 'today':
            return (today, today)
        if date_filter == 'week':
            start = today - timedelta(days=today.weekday())
            return (start, today)
        if date_filter == 'month':
            start = today.replace(day=1)
            return (start, today)
        if date_filter == 'year':
            start = today.replace(month=1, day=1)
            return (start, today)
        if date_filter == 'custom':
            if state['date_from'] and state['date_to']:
                return (state['date_from'], state['date_to'])
            return (False, False)
        start = today.replace(day=1)
        return (start, today)

    def _empty_subscription_metrics(self):
        return {
            'subscription_cash_amount': 0.0,
            'subscription_card_amount': 0.0,
            'subscription_total_amount': 0.0,
        }

    def _empty_sale_metrics(self):
        return {
            'badminton_sale_cash_amount': 0.0,
            'badminton_sale_card_amount': 0.0,
            'badminton_sale_abonent_amount': 0.0,
            'badminton_sale_total_amount': 0.0,
        }

    def _empty_other_metrics(self):
        return {
            'other_income_amount': 0.0,
            'other_expense_amount': 0.0,
            'other_net_amount': 0.0,
        }

    def _empty_overall_metrics(self):
        return {
            'overall_cash_income': 0.0,
            'overall_card_income': 0.0,
            'overall_total_income': 0.0,
        }

    def _empty_child_metrics(self):
        return {
            'total_children_count': 0,
            'new_children_count': 0,
        }

    def _empty_entry_metrics(self):
        return {
            'cash_entries': 0,
            'card_entries': 0,
            'abonent_entries': 0,
            'onefit_entries': 0,
            'push30_entries': 0,
            'push30_plus_entries': 0,
            'tripsome_entries': 0,
            'total_entries': 0,
        }

    def _get_subscription_payment_sets(self, date_from, date_to):
        """Seçilmiş interval üçün 3 dəst qaytarır:
        - timely: payment_date intervalda olanlar
        - delayed: real_date intervalda, payment_date isə AY-dan kənar olanlar
        - all_for_report: timely ∪ delayed  (reportda istifadə etdiyimiz)
        """
        payment_obj = self.env['badminton.lesson.payment.genclik']

        if not date_from or not date_to:
            empty = payment_obj.browse([])
            return {
                'timely': empty,
                'delayed': empty,
                'all_for_report': empty,
            }

        # 1️⃣ Intervalda payment_date
        timely = payment_obj.search([
            ('payment_date', '>=', date_from),
            ('payment_date', '<=', date_to),
        ])

        # 2️⃣ Intervalda real_date
        payments_real = payment_obj.search([
            ('real_date', '>=', date_from),
            ('real_date', '<=', date_to),
            ('real_date', '!=', False),
        ])

        # 3️⃣ AY aralığını tap (date_from-un ayına görə)
        month_start = date_from.replace(day=1)
        month_end = month_start + relativedelta(months=1, days=-1)

        # 4️⃣ Gecikmiş: real_date intervalda, payment_date AY-dan kənardadır
        delayed = payments_real.filtered(lambda p:
            not p.payment_date or
            p.payment_date < month_start or
            p.payment_date > month_end
        )

        # 5️⃣ Reportda istifadə etdiyimiz dəst:
        # payment_date intervalda OLANLAR + gecikmişlər
        all_for_report = timely | delayed

        return {
            'timely': timely,
            'delayed': delayed,
            'all_for_report': all_for_report,
        }


    def _compute_delayed_payments(self, override=None):
        """
        Gecikmiş ödənişləri hesabla:
        real_date seçilmiş tarix intervalında,
        payment_date isə həmin intervalın AYI üzrə deyil (başqa aydadır).
        """
        state = self._resolve_filter_state(override)
        if state['date_filter'] == 'custom' and (not state['date_from'] or not state['date_to']):
            return {'delayed_payments_amount': 0.0}

        date_from, date_to = self._get_date_range(state)
        if not date_from or not date_to:
            return {'delayed_payments_amount': 0.0}

        sets = self._get_subscription_payment_sets(date_from, date_to)
        delayed_payments = sets['delayed']

        delayed_amount = sum(delayed_payments.mapped('amount'))
        return {'delayed_payments_amount': delayed_amount}


    def _compute_subscription_metrics(self, override=None):
        state = self._resolve_filter_state(override)
        if state['date_filter'] == 'custom' and (not state['date_from'] or not state['date_to']):
            return self._empty_subscription_metrics()

        date_from, date_to = self._get_date_range(state)
        if not date_from or not date_to:
            return self._empty_subscription_metrics()

        sets = self._get_subscription_payment_sets(date_from, date_to)
        all_payments = sets['all_for_report']

        cash_amount = sum(all_payments.filtered(
            lambda p: p.payment_method_lesson == 'cash'
        ).mapped('amount'))

        card_amount = sum(all_payments.filtered(
            lambda p: p.payment_method_lesson == 'card'
        ).mapped('amount'))

        total_amount = cash_amount + card_amount

        return {
            'subscription_cash_amount': cash_amount,
            'subscription_card_amount': card_amount,
            'subscription_total_amount': total_amount,
        }


    def _build_sale_domain(self, date_from, date_to):
        domain = [('state', '=', 'paid')]
        if date_from and date_to:
            start_dt = datetime.combine(date_from, datetime.min.time())
            end_dt = datetime.combine(date_to, datetime.max.time())
            domain += [
                ('payment_date', '>=', start_dt),
                ('payment_date', '<=', end_dt),
            ]
        return domain

    def _compute_badminton_sale_metrics(self, override=None):
        state = self._resolve_filter_state(override)
        if state['date_filter'] == 'custom' and (not state['date_from'] or not state['date_to']):
            return self._empty_sale_metrics()

        date_from, date_to = self._get_date_range(state)
        if not date_from or not date_to:
            return self._empty_sale_metrics()

        sale_obj = self.env['badminton.sale.genclik']
        sales = sale_obj.search(self._build_sale_domain(date_from, date_to))

        cash_amount = sum(sales.filtered(lambda s: s.payment_method == 'cash').mapped('amount_paid'))
        card_amount = sum(sales.filtered(lambda s: s.payment_method == 'card').mapped('amount_paid'))
        abonent_amount = sum(sales.filtered(lambda s: s.payment_method == 'abonent').mapped('amount_paid'))
        total_amount = cash_amount + card_amount + abonent_amount

        return {
            'badminton_sale_cash_amount': cash_amount,
            'badminton_sale_card_amount': card_amount,
            'badminton_sale_abonent_amount': abonent_amount,
            'badminton_sale_total_amount': total_amount,
        }

    def _build_cash_flow_domain(self, date_from, date_to):
        domain = [('sport_type', '=', 'badminton')]
        if date_from and date_to:
            domain += [
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ]
        return domain

    def _compute_other_metrics(self, override=None):
        state = self._resolve_filter_state(override)
        if state['date_filter'] == 'custom' and (not state['date_from'] or not state['date_to']):
            return self._empty_other_metrics()

        date_from, date_to = self._get_date_range(state)
        if not date_from or not date_to:
            return self._empty_other_metrics()

        cash_flow_obj = self.env['volan.cash.flow.genclik']
        base_domain = self._build_cash_flow_domain(date_from, date_to)

        income_domain = base_domain + [
            ('transaction_type', '=', 'income'),
            ('category', '=', 'other'),
        ]
        expense_domain = base_domain + [
            ('transaction_type', '=', 'expense'),
            ('category', '=', 'other'),
        ]

        income_amount = sum(cash_flow_obj.search(income_domain).mapped('amount'))
        expense_amount = sum(cash_flow_obj.search(expense_domain).mapped('amount'))
        net_amount = income_amount - expense_amount

        return {
            'other_income_amount': income_amount,
            'other_expense_amount': expense_amount,
            'other_net_amount': net_amount,
        }

    def _compute_child_metrics(self, override=None):
        lesson_obj = self.env['badminton.lesson.simple.genclik']
        # Yalnız aktiv abunəlikləri say
        all_lessons = lesson_obj.search([('state', '=', 'active')])
        total_children = len(set(all_lessons.mapped('partner_id').ids))

        state = self._resolve_filter_state(override)
        date_from, date_to = self._get_date_range(state)

        new_children = 0
        if date_from and date_to:
            lessons_in_range = lesson_obj.search([
                ('payment_date', '>=', date_from),
                ('payment_date', '<=', date_to),
            ])
            range_partners = set(lessons_in_range.mapped('partner_id').ids)
            earlier_partners = set()
            if date_from:
                earlier_lessons = lesson_obj.search([('payment_date', '<', date_from)])
                earlier_partners = set(earlier_lessons.mapped('partner_id').ids)
            new_children = len(range_partners - earlier_partners)

        return {
            'total_children_count': total_children,
            'new_children_count': new_children,
        }

    def _compute_entry_metrics(self, override=None):
        state = self._resolve_filter_state(override)
        if state['date_filter'] == 'custom' and (not state['date_from'] or not state['date_to']):
            return self._empty_entry_metrics()

        date_from, date_to = self._get_date_range(state)
        if not date_from or not date_to:
            return self._empty_entry_metrics()

        session_obj = self.env['badminton.session.genclik']
        session_domain = [('state', '=', 'completed')]
        start_dt = datetime.combine(date_from, datetime.min.time())
        end_dt = datetime.combine(date_to, datetime.max.time())
        session_domain += [
            ('start_time', '>=', start_dt),
            ('start_time', '<=', end_dt),
        ]
        sessions = session_obj.search(session_domain)

        cash_entries = len(sessions.filtered(lambda s: s.payment_type == 'cash'))
        card_entries = len(sessions.filtered(lambda s: s.payment_type == 'card'))
        abonent_entries = len(sessions.filtered(lambda s: s.payment_type == 'abonent'))
        onefit_entries = len(sessions.filtered(lambda s: s.promo_type == '1fit'))
        push30_entries = len(sessions.filtered(lambda s: s.promo_type == 'push30'))
        push30_plus_entries = len(sessions.filtered(lambda s: s.promo_type == 'push30_plus'))
        tripsome_entries = len(sessions.filtered(lambda s: s.promo_type == 'tripsome'))
        total_entries = len(sessions)

        return {
            'cash_entries': cash_entries,
            'card_entries': card_entries,
            'abonent_entries': abonent_entries,
            'onefit_entries': onefit_entries,
            'push30_entries': push30_entries,
            'push30_plus_entries': push30_plus_entries,
            'tripsome_entries': tripsome_entries,
            'total_entries': total_entries,
        }

    def _compute_overall_metrics(self, metrics):
        cash_income = metrics.get('subscription_cash_amount', 0.0) + metrics.get('badminton_sale_cash_amount', 0.0)
        card_income = metrics.get('subscription_card_amount', 0.0) + metrics.get('badminton_sale_card_amount', 0.0)
        total_income = (cash_income + card_income +
                        metrics.get('badminton_sale_abonent_amount', 0.0) +
                        metrics.get('other_income_amount', 0.0)) - metrics.get('other_expense_amount', 0.0)

        return {
            'overall_cash_income': cash_income,
            'overall_card_income': card_income,
            'overall_total_income': total_income,
        }

    def _compute_all_time_overall_total(self, date_to):
        """Ümumi Qalıq dəyərini 0-cı ildən seçilmiş tarix aralığının sonuna qədər hesablayır."""
        payment_obj = self.env['badminton.lesson.payment.genclik']
        
        # payment_date və ya real_date seçilmiş tarix aralığının sonuna qədər olan ödənişlər
        payment_date_payments = payment_obj.search([('payment_date', '<=', date_to)])
        real_date_payments = payment_obj.search([
            ('real_date', '<=', date_to),
            ('real_date', '!=', False)
        ])
        all_payments = payment_date_payments | real_date_payments
        
        subscription_cash = sum(all_payments.filtered(lambda p: p.payment_method_lesson == 'cash').mapped('amount'))
        subscription_card = sum(all_payments.filtered(lambda p: p.payment_method_lesson == 'card').mapped('amount'))

        sale_obj = self.env['badminton.sale.genclik']
        end_dt = datetime.combine(date_to, datetime.max.time())
        sales = sale_obj.search([('state', '=', 'paid'), ('payment_date', '<=', end_dt)])
        sale_cash = sum(sales.filtered(lambda s: s.payment_method == 'cash').mapped('amount_paid'))
        sale_card = sum(sales.filtered(lambda s: s.payment_method == 'card').mapped('amount_paid'))
        sale_abonent = sum(sales.filtered(lambda s: s.payment_method == 'abonent').mapped('amount_paid'))

        cash_flow_obj = self.env['volan.cash.flow.genclik']
        other_income = sum(cash_flow_obj.search([
            ('sport_type', '=', 'badminton'),
            ('category', '=', 'other'),
            ('transaction_type', '=', 'income'),
            ('date', '<=', date_to),
        ]).mapped('amount'))

        # Xərcləri çıxırıq
        other_expense = sum(cash_flow_obj.search([
            ('sport_type', '=', 'badminton'),
            ('transaction_type', '=', 'expense'),
            ('date', '<=', date_to),
        ]).mapped('amount'))

        return (subscription_cash + subscription_card +
                sale_cash + sale_card + sale_abonent + other_income - other_expense)

    def _compute_cashbox_metrics(self, metrics, override=None):
        state = self._resolve_filter_state(override)
        date_from, date_to = self._get_date_range(state)
        
        if not date_to:
            date_to = fields.Date.today()
            
        all_time_total = self._compute_all_time_overall_total(date_to)
        
        # İlkin Qalıq = seçilmiş intervaldan ƏVVƏL olan balans
        if date_from:
            date_before = date_from - timedelta(days=1)
            initial_balance = self._compute_all_time_overall_total(date_before)
        else:
            initial_balance = 0.0
        
        return {
            'cashbox_balance': all_time_total,
            'initial_balance': initial_balance,
            'overall_total_income': all_time_total,  # Ümumi Qalıq = Son Qalıq
        }

    def _compute_payment_summary(self, metrics):
        cash_payments = metrics.get('subscription_cash_amount', 0.0) + metrics.get('badminton_sale_cash_amount', 0.0)
        card_payments = metrics.get('subscription_card_amount', 0.0) + metrics.get('badminton_sale_card_amount', 0.0)
        abonent_payments = metrics.get('badminton_sale_abonent_amount', 0.0)
        total_payments = cash_payments + card_payments + abonent_payments
        return {
            'cash_payments': cash_payments,
            'card_payments': card_payments,
            'abonent_payments': abonent_payments,
            'total_payments': total_payments,
        }

    def _gather_metrics(self, override=None):
        metrics = {}
        metrics.update(self._compute_subscription_metrics(override=override))
        metrics.update(self._compute_badminton_sale_metrics(override=override))
        metrics.update(self._compute_other_metrics(override=override))
        metrics.update(self._compute_child_metrics(override=override))
        metrics.update(self._compute_delayed_payments(override=override))
        metrics.update(self._compute_overall_metrics(metrics))
        metrics.update(self._compute_entry_metrics(override=override))
        metrics.update(self._compute_payment_summary(metrics))
        metrics.update(self._compute_cashbox_metrics(metrics, override=override))
        return metrics

    def action_refresh(self):
        metrics = self._gather_metrics()
        self.write(metrics)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.onchange('date_filter', 'date_from', 'date_to')
    def _onchange_date_filter(self):
        state = self._resolve_filter_state()
        if state['date_filter'] == 'custom' and (not state['date_from'] or not state['date_to']):
            return
        metrics = self._gather_metrics()
        for field_name, value in metrics.items():
            setattr(self, field_name, value)

    def _open_badminton_cash_view(self, name, domain):
        self.ensure_one()
        state = self._resolve_filter_state()
        date_from, date_to = self._get_date_range(state)
        date_domain = []
        if date_from and date_to:
            date_domain = [('date', '>=', date_from), ('date', '<=', date_to)]

        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'volan.cash.flow.genclik',
            'view_mode': 'list,form',
            'domain': date_domain + domain,
            'context': {'default_sport_type': 'badminton'},
            'target': 'current'
        }

    def show_badminton_sales(self):
        domain = [
            ('sport_type', '=', 'badminton'),
            ('category', '=', 'badminton_sale'),
            ('transaction_type', '=', 'income')
        ]
        return self._open_badminton_cash_view('Badminton Satış Gəlirləri', domain)

    def show_badminton_lessons(self):
        domain = [
            ('sport_type', '=', 'badminton'),
            ('category', '=', 'badminton_lesson'),
            ('transaction_type', '=', 'income')
        ]
        return self._open_badminton_cash_view('Badminton Dərs Gəlirləri', domain)

    def show_badminton_other_income(self):
        domain = [
            ('sport_type', '=', 'badminton'),
            ('category', 'not in', ['badminton_sale', 'badminton_lesson']),
            ('transaction_type', '=', 'income')
        ]
        return self._open_badminton_cash_view('Digər Badminton Gəlirləri', domain)

    def show_badminton_expenses(self):
        domain = [
            ('sport_type', '=', 'badminton'),
            ('transaction_type', '=', 'expense')
        ]
        return self._open_badminton_cash_view('Badminton Xərcləri', domain)

    # ---------------- Helpers ----------------
    def _ensure_one_and_get_range(self):
        self.ensure_one()
        state = self._resolve_filter_state()
        date_from, date_to = self._get_date_range(state)
        return date_from, date_to

    def _act_window(self, name, res_model, domain, context=None):
        ctx = dict(self.env.context)
        if context:
            ctx.update(context)
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "target": "current",
            "domain": domain,
            "context": ctx,
        }

    # ---------------- 1) Abunəlik (badminton.lesson.payment) ----------------
    def action_view_subscription_cash(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sets = self._get_subscription_payment_sets(date_from, date_to)
        payments = sets["all_for_report"].filtered(lambda p: p.payment_method_lesson == "cash")
        return self._act_window("Abunəlik Nağd Ödənişləri", "badminton.lesson.payment.genclik", [("id", "in", payments.ids)])

    def action_view_subscription_card(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sets = self._get_subscription_payment_sets(date_from, date_to)
        payments = sets["all_for_report"].filtered(lambda p: p.payment_method_lesson == "card")
        return self._act_window("Abunəlik Kart Ödənişləri", "badminton.lesson.payment.genclik", [("id", "in", payments.ids)])

    def action_view_subscription_total(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sets = self._get_subscription_payment_sets(date_from, date_to)
        payments = sets["all_for_report"]
        return self._act_window("Abunəlik Ödənişləri (Ümumi)", "badminton.lesson.payment.genclik", [("id", "in", payments.ids)])

    def action_view_delayed_payments(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sets = self._get_subscription_payment_sets(date_from, date_to)
        payments = sets["delayed"]
        return self._act_window("Gecikmiş Ödənişlər", "badminton.lesson.payment.genclik", [("id", "in", payments.ids)])

    # ---------------- 2) Badminton Satışı (badminton.sale) ----------------
    def action_view_badminton_sale_cash(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sales = self.env["badminton.sale.genclik"].search(self._build_sale_domain(date_from, date_to) + [("payment_method", "=", "cash")])
        return self._act_window("Badminton Satışı (Nağd)", "badminton.sale.genclik", [("id", "in", sales.ids)])

    def action_view_badminton_sale_card(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sales = self.env["badminton.sale.genclik"].search(self._build_sale_domain(date_from, date_to) + [("payment_method", "=", "card")])
        return self._act_window("Badminton Satışı (Kart)", "badminton.sale.genclik", [("id", "in", sales.ids)])

    def action_view_badminton_sale_abonent(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sales = self.env["badminton.sale.genclik"].search(self._build_sale_domain(date_from, date_to) + [("payment_method", "=", "abonent")])
        return self._act_window("Badminton Satışı (Abunəçi)", "badminton.sale.genclik", [("id", "in", sales.ids)])

    def action_view_badminton_sale_total(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sales = self.env["badminton.sale.genclik"].search(self._build_sale_domain(date_from, date_to))
        return self._act_window("Badminton Satışı (Ümumi)", "badminton.sale.genclik", [("id", "in", sales.ids)])

    # ---------------- 3) Digər Mədaxil/Məxaric (volan.cash.flow) ----------------
    def action_view_other_income(self):
        date_from, date_to = self._ensure_one_and_get_range()
        domain = self._build_cash_flow_domain(date_from, date_to) + [
            ("transaction_type", "=", "income"),
            ("category", "=", "other"),
        ]
        return self._act_window("Digər Mədaxil", "volan.cash.flow.genclik", domain, context={"default_sport_type": "badminton"})

    def action_view_other_expense(self):
        date_from, date_to = self._ensure_one_and_get_range()
        domain = self._build_cash_flow_domain(date_from, date_to) + [
            ("transaction_type", "=", "expense"),
            ("category", "=", "other"),
        ]
        return self._act_window("Digər Məxaric", "volan.cash.flow.genclik", domain, context={"default_sport_type": "badminton"})

    def action_view_other_net(self):
        date_from, date_to = self._ensure_one_and_get_range()
        domain = self._build_cash_flow_domain(date_from, date_to) + [("category", "=", "other")]
        return self._act_window("Digər Axınlar (Net detalları)", "volan.cash.flow.genclik", domain, context={"default_sport_type": "badminton"})

    # ---------------- 4) Giriş Hesabatı (badminton.session) ----------------
    def _sessions_in_range(self, date_from, date_to):
        start_dt = datetime.combine(date_from, datetime.min.time())
        end_dt = datetime.combine(date_to, datetime.max.time())
        return self.env["badminton.session.genclik"].search([
            ("state", "=", "completed"),
            ("start_time", ">=", start_dt),
            ("start_time", "<=", end_dt),
        ])

    def action_view_entries_cash(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.payment_type == "cash")
        return self._act_window("Girişlər (Nağd)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    def action_view_entries_card(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.payment_type == "card")
        return self._act_window("Girişlər (Card to card)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    def action_view_entries_abonent(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.payment_type == "abonent")
        return self._act_window("Girişlər (Abunəçi)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    # ---------------- 5) Tətbiq Hesabatı (badminton.session promo_type) ----------------
    def action_view_app_onefit(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.promo_type == "1fit")
        return self._act_window("Tətbiq Girişləri (1FIT)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    def action_view_app_push30(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.promo_type == "push30")
        return self._act_window("Tətbiq Girişləri (PUSH30)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    def action_view_app_push30_plus(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.promo_type == "push30_plus")
        return self._act_window("Tətbiq Girişləri (PUSH30+)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    def action_view_app_tripsome(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to).filtered(lambda s: s.promo_type == "tripsome")
        return self._act_window("Tətbiq Girişləri (Tripsome)", "badminton.session.genclik", [("id", "in", sessions.ids)])

    def action_view_entries_total(self):
        date_from, date_to = self._ensure_one_and_get_range()
        sessions = self._sessions_in_range(date_from, date_to)
        return self._act_window("Girişlər (Ümumi)", "badminton.session.genclik", [("id", "in", sessions.ids)])
