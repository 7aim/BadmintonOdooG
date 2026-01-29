# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from calendar import monthrange

STATE_SELECTION = [
    ('draft', 'Təsdiqlənməyib'),
    ('active', 'Aktiv'),
    ('cancel_requested', 'Ləğv Tələbi'),
    ('cancelled', 'Ləğv Edilib'),
    ('restore_requested', 'Bərpa Tələbi'),
    ('free', 'Ödənişsizlər'),

    ('completed', 'Tamamlanıb'),
]

class BadmintonLessonSimple(models.Model):
    _name = 'badminton.lesson.simple.genclik'
    _description = 'Badminton Dərsi'
    _order = 'create_date desc'
    _temp_states = ('free', 'cancel_requested')
    
    name = fields.Char(string="Dərs Nömrəsi", readonly=True, default="Yeni")
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    group_ids = fields.Many2many('badminton.group.genclik', string="Qruplar")
    
    # Paket seçimi - badminton paketləri
    package_id = fields.Many2one('badminton.package.genclik', string="Abunəlik Paketi",
                                  domain="[('active', '=', True), ('package_type', '=', 'monthly')]")

    # Dərs Qrafiki (həftənin günləri)
    schedule_ids = fields.One2many('badminton.lesson.schedule.simple.genclik', 'lesson_id', string="Həftəlik Qrafik")
    
    # İştiraklar
    attendance_ids = fields.One2many('badminton.lesson.attendance.simple.genclik', 'lesson_id', string="Dərsə İştiraklar")
    total_attendances = fields.Integer(string="Ümumi İştirak", compute='_compute_total_attendances')
    current_month_attendances = fields.Integer(string="İştirak Sayı", compute='_compute_current_month_attendances', 
                                                help="Ən son ödəniş tarixindən sonrakı iştiraklar")
    substitute_ids = fields.One2many('badminton.lesson.substitute.genclik', 'lesson_id', string="Əvəzedici Dərslər")
    substitute_count = fields.Integer(string="Əvəzedici Dərs Sayı", compute='_compute_substitute_count', store=True)
    
    # Ödəniş məlumatları
    lesson_fee = fields.Float(string="Aylıq Dərs Haqqı", default=100.0, store=True)
    original_price = fields.Float(string="Endirimsiz Qiymət", readonly=True)
    
    # Tarix məlumatları
    start_date = fields.Date(string="Cari Dövr Başlama", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Cari Dövr Bitmə", compute='_compute_end_date', store=True, readonly=False)
    
    # Ödənişlər (One2Many)
    payment_ids = fields.One2many('badminton.lesson.payment.genclik', 'lesson_id', string="Ödənişlər", ondelete='restrict')
    last_payment_date = fields.Date(string="Ən Son Ödəniş", compute='_compute_last_payment_date', store=True)
    
    # Abunəlik məlumatları (ödənişlərə əsasən hesablanır)
    total_months = fields.Integer(string="Ümumi Abunəlik (ay)", compute='_compute_total_months', store=True)
    total_payments = fields.Float(string="Ümumi Ödəniş", compute='_compute_total_payments', store=True)
    
    # Dondurma məlumatları
    freeze_ids = fields.One2many('badminton.lesson.freeze.genclik', 'lesson_id', string="Dondurma Tarixçəsi")
    total_freeze_days = fields.Integer(string="Ümumi Donma Günləri", compute='_compute_total_freeze_days', store=True)
    current_freeze_id = fields.Many2one('badminton.lesson.freeze.genclik', string="Cari Dondurma", compute='_compute_current_freeze', store=True)
    
    # Vəziyyət
    state = fields.Selection(STATE_SELECTION, default='draft', string="Vəziyyət")
    previous_state = fields.Selection(STATE_SELECTION, string="Öncəki Status", readonly=True)
    
    # Ödəniş tarixi (sabit - kassaya təsir edən gün)
    payment_date = fields.Date(string="Başlama Tarixi", required=True, default=fields.Date.today,
                                help="İlkin başlanğıc tarixi (informativ)")
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")
    zero_fee_reason = fields.Text(string="Ödənişsiz səbəb")
    
    # Abunəlik ödəniş statusu (rəng üçün)
    subscription_payment_status = fields.Selection([
        ('on_time', 'Vaxtında'),
        ('warning', 'Xəbərdarlıq'),
        ('overdue', 'Vaxtından keçmiş'),
    ], string="Abunəlik Ödəniş Statusu", compute='_compute_subscription_payment_status', store=True)

    @api.depends('payment_date', 'payment_ids.payment_date')
    def _compute_end_date(self):
        for lesson in self:
            # baza gün (başlama/payment_date gününü saxlayırıq)
            base_day = lesson.payment_date.day if lesson.payment_date else False

            # ən son ödəniş sətri (payment_date-ə görə)
            payments = lesson.payment_ids.filtered(lambda p: p.payment_date)
            last_date = payments.sorted('payment_date')[-1].payment_date if payments else False

            # heç ödəniş yoxdursa fallback: lesson.payment_date
            base_date = last_date or lesson.payment_date

            if not base_date:
                lesson.end_date = False
                continue

            next_month = base_date + relativedelta(months=1)

            # günü ayın maksimum gününə “clamp” edirik
            day = base_day or next_month.day
            max_day = monthrange(next_month.year, next_month.month)[1]
            lesson.end_date = next_month.replace(day=min(day, max_day))

    @api.onchange('payment_date')
    def _onchange_payment_date(self):
        """Başlama tarixi dəyişəndə bitmə tarixini yenilə"""
        self._compute_end_date()

    @api.depends('payment_date', 'payment_ids', 'payment_ids.payment_date')
    def _compute_subscription_payment_status(self):
        """Başlanğıc tarixindən bu günə qədər hər ay üçün ödəniş olub-olmadığını yoxla"""
        today = fields.Date.today()
        for lesson in self:
            if not lesson.payment_date:
                lesson.subscription_payment_status = 'on_time'
                continue
            
            # Başlanğıc tarixindən bu günə qədər neçə ay keçib?
            start_date = lesson.payment_date
            
            # Əgər başlama tarixi gələcəkdədirsə, hələ ödəniş lazım deyil
            if start_date > today:
                lesson.subscription_payment_status = 'on_time'
                continue
            
            # Başlanğıcdan bu günə qədər olan ayları yarat
            current_check = start_date.replace(day=1)  # Başlanğıc ayının 1-i
            today_month_start = today.replace(day=1)   # Bu ayın 1-i
            
            missing_months = []
            while current_check <= today_month_start:
                # Bu ay üçün ödəniş var mı?
                payment_found = False
                for payment in lesson.payment_ids:
                    if payment.payment_date:
                        # payment_date hansı aya aiddir?
                        pay_month_start = payment.payment_date.replace(day=1)
                        if pay_month_start == current_check:
                            payment_found = True
                            break
                
                if not payment_found:
                    missing_months.append(current_check)
                
                # Növbəti aya keç
                current_check = current_check + relativedelta(months=1)
            
            # Əgər ödənilməmiş ay varsa
            if missing_months:
                # Ən son ödənilməmiş ay (prioritet: ən köhnə ödənilməmiş)
                first_missing = missing_months[0]
                payment_day = lesson.payment_date.day
                
                # Bu ay üçün gözlənilən ödəniş tarixi
                max_day_in_month = monthrange(first_missing.year, first_missing.month)[1]
                expected_day = min(payment_day, max_day_in_month)
                expected_payment_date = first_missing.replace(day=expected_day)
                
                # 5 gün əvvəl xəbərdarlıq
                warning_date = expected_payment_date - timedelta(days=5)
                
                if today >= expected_payment_date:
                    lesson.subscription_payment_status = 'overdue'
                elif today >= warning_date:
                    lesson.subscription_payment_status = 'warning'
                else:
                    lesson.subscription_payment_status = 'on_time'
            else:
                lesson.subscription_payment_status = 'on_time'

    """
    @api.depends('start_date')
    def _compute_end_date(self):
        for lesson in self:
            if lesson.start_date:
                # 1 ay əlavə et
                lesson.end_date = lesson.start_date + timedelta(days=30)
            else:
                lesson.end_date = False
    """
    
    @api.depends('payment_ids')
    def _compute_last_payment_date(self):
        """Ən son ödənişin tarixini hesabla"""
        for lesson in self:
            payments_with_real_date = lesson.payment_ids.filtered(lambda p: p.real_date)
            if payments_with_real_date:
                latest_payment = payments_with_real_date.sorted('real_date', reverse=True)
                lesson.last_payment_date = latest_payment[0].real_date if latest_payment else False
            elif lesson.payment_ids:
                latest_payment = lesson.payment_ids.sorted('payment_date', reverse=True)
                lesson.last_payment_date = latest_payment[0].payment_date if latest_payment else False
            else:
                lesson.last_payment_date = False
    
    @api.depends('payment_ids')
    def _compute_total_months(self):
        """Ümumi abunəlik ayını ödənişlərə əsasən hesabla (hər sətir 1 ay)"""
        for lesson in self:
            lesson.total_months = len(lesson.payment_ids)
    
    @api.depends('payment_ids.amount')
    def _compute_total_payments(self):
        """Ümumi ödənişi hesabla"""
        for lesson in self:
            lesson.total_payments = sum(lesson.payment_ids.mapped('amount'))
    
    @api.depends('attendance_ids')
    def _compute_total_attendances(self):
        for lesson in self:
            lesson.total_attendances = len(lesson.attendance_ids)
    
    @api.depends('attendance_ids.attendance_date', 'last_payment_date')
    def _compute_current_month_attendances(self):
        """Ən son ödəniş tarixindən sonra neçə dəfə dərsə gəldi"""
        for lesson in self:
            if lesson.last_payment_date and lesson.attendance_ids:
                attendances_after_payment = lesson.attendance_ids.filtered(
                    lambda a: a.attendance_date and a.attendance_date > lesson.last_payment_date
                )
                lesson.current_month_attendances = len(attendances_after_payment)
            else:
                lesson.current_month_attendances = len(lesson.attendance_ids)

    @api.depends('substitute_ids')
    def _compute_substitute_count(self):
        for lesson in self:
            lesson.substitute_count = len(lesson.substitute_ids)
            
    @api.depends('freeze_ids.freeze_days', 'freeze_ids.state')
    def _compute_total_freeze_days(self):
        for lesson in self:
            total_days = 0
            for freeze in lesson.freeze_ids.filtered(lambda f: f.state in ['active', 'completed']):
                total_days += freeze.freeze_days
            lesson.total_freeze_days = total_days
            
    @api.depends('freeze_ids.state', 'freeze_ids.freeze_start_date', 'freeze_ids.freeze_end_date')
    def _compute_current_freeze(self):
        today = fields.Date.today()
        for lesson in self:
            current_freeze = lesson.freeze_ids.filtered(lambda f: 
                f.state == 'active' and 
                f.freeze_start_date <= today and 
                f.freeze_end_date >= today
            )
            lesson.current_freeze_id = current_freeze[0].id if current_freeze else False
            lesson.total_attendances = len(lesson.attendance_ids)

    @api.onchange('group_id')
    def _onchange_group_id(self):
        """Qrup seçildikdə avtomatik qrafik əlavə et"""
        if self.group_id:
            # Əvvəlki qrafiki sil
            self.schedule_ids = [(5, 0, 0)]
            
            # Qrupun qrafikini kopyala
            schedule_vals = []
            for group_schedule in self.group_id.schedule_ids:
                if group_schedule.is_active:
                    schedule_vals.append((0, 0, {
                        'day_of_week': group_schedule.day_of_week,
                        'start_time': group_schedule.start_time,
                        'end_time': group_schedule.end_time,
                        'is_active': True,
                        'notes': f"Qrup qrafiki: {self.group_id.name}"
                    }))
            
            if schedule_vals:
                self.schedule_ids = schedule_vals
    
    @api.onchange('package_id')
    def _onchange_package_id(self):
        """Paket seçildikdə avtomatik qiyməti və endirimli qiyməti təyin et"""
        if self.package_id:
            # Varsayılan olaraq böyük qiymətini göstəririk
            base_price = self.package_id.adult_price
            self.original_price = base_price
            discount = self.package_id.discount_percent or 0.0
            
            # Endirimli qiyməti hesablayırıq
            if discount > 0:
                self.lesson_fee = base_price * (1 - discount / 100)
            else:
                self.lesson_fee = base_price
        else:
            self.original_price = 0.0
    
    @api.onchange('group_ids')
    def _onchange_group_ids(self):
        """Qruplar dəyişəndə qrafiki preview göstər (virtual)"""
        if not self.group_ids:
            self.schedule_ids = [(5, 0, 0)]  # Hamısını sil
            return
        
        # Virtual schedule list yaradırıq (hələ DB-də yaradılmır)
        schedule_commands = [(5, 0, 0)]  # Əvvəlcə köhnələri sil
        
        for group in self.group_ids:
            for group_schedule in group.schedule_ids.filtered(lambda s: s.is_active):
                schedule_commands.append((0, 0, {
                    'day_of_week': group_schedule.day_of_week,
                    'start_time': group_schedule.start_time,
                    'end_time': group_schedule.end_time,
                    'is_active': True,
                    'notes': f"Qrup qrafiki: {group.name}"
                }))
        
        self.schedule_ids = schedule_commands
    
    def _sync_schedule_with_groups(self):
        """Seçilmiş qrupların qrafiklərini abunəlik qrafiki ilə sinxronlaşdır (actual DB update)"""
        if not self.id:  # Record hələ yaradılmayıbsa
            return
            
        self.ensure_one()
        
        # Mövcud qrafiki təmizlə (yalnız qrup əsaslı olanları)
        self.schedule_ids.filtered(lambda s: 'Qrup qrafiki:' in (s.notes or '')).unlink()
        
        # Seçilmiş qrupların qrafiklərini əlavə et
        for group in self.group_ids:
            for group_schedule in group.schedule_ids.filtered(lambda s: s.is_active):
                self.env['badminton.lesson.schedule.simple.genclik'].create({
                    'lesson_id': self.id,
                    'day_of_week': group_schedule.day_of_week,
                    'start_time': group_schedule.start_time,
                    'end_time': group_schedule.end_time,
                    'is_active': True,
                    'notes': f"Qrup qrafiki: {group.name}"
                })
    
    @api.model
    def create(self, vals):
        # Abunəlik adı: A-MUSTERIID formatında
        #if vals.get('lesson_fee', 0) <= 0:
            #raise ValidationError("Dərs haqqı 0-dan böyük olmalıdır!") 
        if vals.get('partner_id'):
            partner_id = vals['partner_id']
            vals['name'] = f"A-{partner_id}"
        else:
            vals['name'] = 'A-0'  # Müştəri yoxdursa

        lesson = super(BadmintonLessonSimple, self).create(vals)

        if lesson._is_zero_fee(lesson.lesson_fee):
            lesson._set_state_with_history('free')
        
        # Qrup seçilmişsə qrafiki sinxronlaşdır
        if lesson.group_ids:
            lesson._sync_schedule_with_groups()
        
        # Əgər yaradılan zaman state=active isə və ödəniş yoxdursa, avtomatik ilk ödəniş yarat
        if lesson.state == 'active' and not lesson.payment_ids:
            lesson._create_initial_payment()
        
        return lesson
    
    def write(self, vals):

        # Başlama tarixini dəyişməyə icazə: yalnız admin və ya restore_requested statusuna keçərkən
        #if 'payment_date' in vals and self.env.user.login != 'admin':
            # Əgər restore_requested statusuna keçirikssə, icazə ver
        #    if vals.get('state') != 'restore_requested':
        #        for rec in self:
        #            if rec.payment_date:
        #                raise ValidationError("Başlama tarixi bir dəfə təyin edildikdən sonra dəyişdirilə bilməz.")

        """State və qrup dəyişdikdə müvafiq əməliyyatlar aparır"""
        lesson_fee_updated = 'lesson_fee' in vals
        state_updated = 'state' in vals

        if state_updated and vals.get('state') not in self._temp_states:
            self._clear_previous_state()

        result = super(BadmintonLessonSimple, self).write(vals)

        if lesson_fee_updated:
            zero_fee_records = self.filtered(lambda l: self._is_zero_fee(l.lesson_fee))
            zero_fee_records._set_state_with_history('free')
        
        # Əgər qruplar dəyişdirilirsə qrafiki yenilə
        if 'group_ids' in vals:
            for lesson in self:
                lesson._sync_schedule_with_groups()
        
        # Əgər state active-ə dəyişdirilirsə və ödəniş yoxdursa
        if vals.get('state') == 'active':
            for lesson in self:
                if not lesson.payment_ids:
                    lesson._create_initial_payment()
        
        return result
    
    def _create_initial_payment(self):
        """İlk ödəniş sətirini yarat (helper method)"""
        self.ensure_one()
        
        default_due_date = self.payment_date or fields.Date.today()

        self.env['badminton.lesson.payment.genclik'].create({
            'lesson_id': self.id,
            'payment_date': fields.Date.today(),
            'real_date': default_due_date,
            'amount': self.lesson_fee,
            'notes': 'İlk abunəlik ödənişi (avtomatik)'
        })

    @staticmethod
    def _is_zero_fee(amount):
        return float_compare(amount or 0.0, 0.0, precision_digits=2) == 0

    def _set_state_with_history(self, new_state):
        for lesson in self:
            if lesson.state == new_state:
                continue

            updates = {'state': new_state}
            if new_state in self._temp_states:
                if lesson.state in self._temp_states:
                    prev_state = lesson.previous_state
                else:
                    prev_state = lesson.state
                updates['previous_state'] = prev_state
            else:
                updates['previous_state'] = False

            super(BadmintonLessonSimple, lesson).write(updates)

    def _clear_previous_state(self):
        for lesson in self.filtered('previous_state'):
            super(BadmintonLessonSimple, lesson).write({'previous_state': False})

    def action_confirm(self):
        """Dərsi təsdiqlə və ödənişi qəbul et"""
        for lesson in self:
            if lesson.state == 'draft':
                lesson.state = 'active'
                # write() metodu avtomatik _create_initial_payment() çağıracaq
    
    def action_cancel_request(self):
        """Dərsin ləğv edilməsini tələb et"""
        eligible = self.filtered(lambda l: l.state in ['draft', 'active']) #['draft', 'active', 'frozen']
        eligible._set_state_with_history('cancel_requested')

    
    def action_return_cancelled(self):
        """Ləğv edilmiş abunəliyi geri qaytar - restore_requested statusuna keçir"""
        for lesson in self:
            if lesson.state != 'cancelled':
                continue
            # Başlama tarixini bugünə təyin et və bərpa tələbi statusuna keçir (eyni anda)
            lesson.write({
                'payment_date': fields.Date.today(),
                'state': 'restore_requested'
            })
    
    def action_restore(self):
        """Admin restore_requested abunəlikləri əvvəlki statusuna qaytarır"""
        for lesson in self:
            if lesson.state != 'restore_requested':
                continue
            
            # Əgər 0 AZN-dirsə, qaytaranda da 'free' olsun
            target_state = 'free' if lesson._is_zero_fee(lesson.lesson_fee) else 'active'
            
            # write() içindəki məntiq işləsin (active olarsa ödəniş yoxdursa avtomatik ilk ödəniş yaratsın)
            lesson.write({'state': target_state})


    def action_complete(self):
        for lesson in self:
            if lesson.state == 'active':
                lesson.state = 'completed'
    
    def action_freeze(self):
        """Abunəliyi dondur - Wizard aç"""
        for lesson in self:
            if lesson.state == 'active':
                return {
                    'name': 'Badminton Abunəliyi Dondur',
                    'type': 'ir.actions.act_window',
                    'res_model': 'badminton.lesson.freeze.wizard.genclik',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_lesson_id': lesson.id,
                        'default_partner_id': lesson.partner_id.id,
                        'default_freeze_start_date': fields.Date.today(),
                        'default_freeze_end_date': fields.Date.today() + timedelta(days=7),  # Default 1 week
                    }
                }
    
    def action_unfreeze(self):
        for lesson in self:
            if lesson.state == 'frozen' and lesson.current_freeze_id:
                # Cari dondurmanı tamamlandı kimi işarələ
                lesson.current_freeze_id.action_complete()
                # Yeni end_date hesabla - donma günləri qədər uzat
                if lesson.end_date:
                    freeze_days = lesson.current_freeze_id.freeze_days
                    lesson.end_date = lesson.end_date + timedelta(days=freeze_days)
                # Abunəliyi aktiv et
                lesson.state = 'active'
    
    def action_cancel(self):
        """Dərsi ləğv et"""
        for lesson in self:
            if lesson.state in ['draft', 'active', 'frozen']:
                lesson.state = 'cancelled'

    def action_restore_previous_state(self):
        for lesson in self:
            if lesson.state == 'cancel_requested':
                super(BadmintonLessonSimple, lesson).write({
                    'state': 'cancelled',
                    'previous_state': False,
                })
            elif lesson.state == 'free':
                super(BadmintonLessonSimple, lesson).write({
                    'state': 'active',
                    'previous_state': False,
                })
            #elif lesson.previous_state:
            #    super(BadmintonLessonSimple, lesson).write({
            #        'state': lesson.previous_state,
            #        'previous_state': False,
            #    })
    
    def action_recompute_subscription_status(self):
        """Manual olaraq abunəlik ödəniş statusunu yenilə (Admin üçün)"""
        self._compute_subscription_payment_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Uğurlu',
                'message': f'{len(self)} abunəliyin statusu yeniləndi',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def cron_update_subscription_payment_status(self):
        """Scheduled action - hər gün bütün aktiv abunəliklərin statusunu yenilə"""
        active_lessons = self.search([('state', 'in', ['draft', 'active', 'frozen'])])
        active_lessons._compute_subscription_payment_status()
        return True
    
    @api.constrains('lesson_fee', 'zero_fee_reason')
    def _check_zero_fee_reason(self):
        for lesson in self:
            if lesson.lesson_fee is None:
                continue
            if lesson.lesson_fee < 0:
                raise ValidationError("Dərs haqqı mənfi ola bilməz.")
            if self._is_zero_fee(lesson.lesson_fee) and not lesson.zero_fee_reason:
                raise ValidationError("0 AZN üçün səbəb daxil edilməlidir.")

    @api.onchange('lesson_fee')
    def _onchange_lesson_fee(self):
        if self.lesson_fee is None:
            return
        if self.lesson_fee < 0:
            warning = {
                'title': 'Yanlış məbləğ',
                'message': 'Dərs haqqı mənfi ola bilməz. Zəhmət olmasa müsbət məbləğ daxil edin.'
            }
            self.lesson_fee = 0.0
            return {'warning': warning}
        if self._is_zero_fee(self.lesson_fee):
            return {
                'warning': {
                    'title': 'Ödənişsiz abunəlik',
                    'message': 'Abunəlik haqqını 0 etdiniz. Zəhmət olmasa "Ödənişsiz səbəb" sahəsini doldurun.'
                }
            }

    def unlink(self):
        """Ödənişləri olan abunəliyi silməyə icazə vermə"""
        for lesson in self:
            # Ödənişləri yoxla
            payments = self.env['badminton.lesson.payment.genclik'].search([
                ('lesson_id', '=', lesson.id)
            ])
            if payments:
                raise ValidationError(
                    f'⛔ Bu abunəliyi silmək mümkün deyil!\n\n'
                    f'Abunəlik: {lesson.name}\n'
                    f'Ödəniş sətiirləri sayı: {len(payments)}\n\n'
                    f'💡 Əvvəlcə bütün ödəniş sətirlərini silməlisiniz!'
                )
        
        return super(BadmintonLessonSimple, self).unlink()

class badmintonLessonScheduleSimple(models.Model):
    _name = 'badminton.lesson.schedule.simple.genclik'
    _description = 'Həftəlik Dərs Qrafiki (Sadə)'
    _order = 'day_of_week, start_time'
    
    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Dərs", required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='lesson_id.partner_id', string="Müştəri", store=True)
    
    # Həftənin günü
    day_of_week = fields.Selection([
        ('0', 'Bazar ertəsi'),
        ('1', 'Çərşənbə axşamı'),
        ('2', 'Çərşənbə'),
        ('3', 'Cümə axşamı'),
        ('4', 'Cümə'),
        ('5', 'Şənbə'),
        ('6', 'Bazar')
    ], string="Həftənin Günü", required=True)
    
    # Vaxt aralığı
    start_time = fields.Float(string="Başlama Vaxtı", required=True, help="Məsələn 19.5 = 19:30")
    end_time = fields.Float(string="Bitmə Vaxtı", required=True, help="Məsələn 20.5 = 20:30")
    
    # Aktivlik
    is_active = fields.Boolean(string="Aktiv", default=True)
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")

    def name_get(self):
        """Dərs vaxtını daha anlaşıqlı formada göstər"""
        result = []
        day_names = dict(self._fields['day_of_week'].selection)
        for schedule in self:
            start_hours = int(schedule.start_time)
            start_minutes = int((schedule.start_time - start_hours) * 60)
            end_hours = int(schedule.end_time)
            end_minutes = int((schedule.end_time - end_hours) * 60)
            
            formatted_time = f"{day_names[schedule.day_of_week]} {start_hours:02d}:{start_minutes:02d}-{end_hours:02d}:{end_minutes:02d}"
            result.append((schedule.id, formatted_time))
        return result 

    @api.constrains('start_time', 'end_time')
    def _check_time_range(self):
        for schedule in self:
            if schedule.start_time >= schedule.end_time:
                raise ValidationError("Başlama vaxtı bitmə vaxtından kiçik olmalıdır!")
            if schedule.start_time < 0 or schedule.start_time > 24:
                raise ValidationError("Başlama vaxtı 0-24 aralığında olmalıdır!")
            if schedule.end_time < 0 or schedule.end_time > 24:
                raise ValidationError("Bitmə vaxtı 0-24 aralığında olmalıdır!")
            
class badmintonLessonAttendanceSimple(models.Model):
    _name = 'badminton.lesson.attendance.simple.genclik'
    _description = 'Badminton Dərs İştirakı (Sadə)'
    _order = 'attendance_date desc, attendance_time desc'

    lesson_id = fields.Many2one('badminton.lesson.simple.genclik', string="Dərs Abunəliyi", required=True)
    schedule_id = fields.Many2one('badminton.lesson.schedule.simple.genclik', string="Dərs Qrafiki", required=False, ondelete='set null')
    partner_id = fields.Many2one(related='lesson_id.partner_id', string="Müştəri", store=True)
    
    # İştirak məlumatları
    attendance_date = fields.Date(string="İştirak Tarixi", default=fields.Date.today)
    attendance_time = fields.Datetime(string="İştirak Vaxtı", default=fields.Datetime.now)
    
    # QR scan məlumatları  
    qr_scanned = fields.Boolean(string="QR ilə Giriş", default=True)
    scan_result = fields.Text(string="QR Nəticəsi")
    
    # Qeydlər
    notes = fields.Text(string="Qeydlər")