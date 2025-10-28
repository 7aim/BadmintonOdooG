# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class BadmintonSession(models.Model):
    _name = 'badminton.session.genclik'
    _description = 'Badminton Oyun Sessiyası'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc'

    name = fields.Char(string="Sessiya Nömrəsi", readonly=True, default="Yeni")
    partner_id = fields.Many2one('res.partner', string="Müştəri", required=True)
    start_time = fields.Datetime(string="Başlama Vaxtı", readonly=True)
    end_time = fields.Datetime(string="Bitmə Vaxtı", readonly=True)
    duration_hours = fields.Float(string="Müddət (saat)", default=1.0, required=True)

    promo_type = fields.Selection([
        ('1fit', '1FIT'),
        ('push30', 'PUSH30'),
    ], string="Tətbiq")

    state = fields.Selection([
        ('draft', 'Gözləmədə'),
        ('active', 'Aktiv'),
        ('extended', 'Uzadılıb'),
        ('completed', 'Tamamlanıb'),
        ('cancelled', 'Ləğv edilib')
    ], string="Vəziyyət", default='draft')

    qr_scanned = fields.Boolean(string="QR Oxunub", default=False)
    extended_time = fields.Float(string="Əlavə Vaxt (saat)", default=0.0)
    notes = fields.Text(string="Qeydlər")
    time_expired = fields.Boolean(string="Vaxt Bitib", compute="_compute_time_expired", store=False)
    completion_time = fields.Datetime(string="Tamamlanma Vaxtı")
    recently_completed = fields.Boolean(string="Son Tamamlanan", compute="_compute_recently_completed", store=True)
    
    # Növbə sistemi
    queue_number = fields.Integer(string="Növbə", compute="_compute_queue_number", store=False, readonly=True)
    created_at = fields.Datetime(string="Yaradılma Vaxtı", default=fields.Datetime.now, readonly=True)

    # one-time flag, чтобы не спамить одно и то же окончание
    warn10_sent = fields.Boolean(string="10 dəq xəbərdarlığı göndərilib", default=False, index=True)

    # ---------- computed ----------
    @api.depends('end_time', 'state')
    def _compute_time_expired(self):
        now = fields.Datetime.now()
        for r in self:
            r.time_expired = bool(r.end_time and r.state in ('active', 'extended') and now > r.end_time)

    @api.depends('state', 'completion_time')
    def _compute_recently_completed(self):
        now = fields.Datetime.now()
        for r in self:
            if r.state == 'completed' and r.completion_time:
                r.recently_completed = (now - r.completion_time).total_seconds() < 900
            else:
                r.recently_completed = False
    
    def _compute_queue_number(self):
        """Gözləmədə olan sessiyalar üçün növbə nömrəsini hesabla"""
        for rec in self:
            if rec.state == 'draft':
                # Gözləmədə olan və bu sessiyadan əvvəl yaradılmış sessiyaları say
                queue_position = self.search_count([
                    ('state', '=', 'draft'),
                    ('created_at', '<', rec.created_at),
                    ('id', '!=', rec.id)
                ])
                rec.queue_number = queue_position + 1
            else:
                rec.queue_number = 0
    
    def _get_max_capacity(self):
        """Zal kapasiteti - System Parameter-dən oxunur"""
        capacity = self.env['ir.config_parameter'].sudo().get_param(
            'volan_genclikk.badminton_court_capacity', 
            default='6'
        )
        return int(capacity)
    
    def _get_active_sessions_count(self):
        """Hal-hazırda aktiv və uzadılmış sessiyaların sayı"""
        return self.search_count([
            ('state', 'in', ['active', 'extended'])
        ])
    
    def _check_capacity(self):
        """Zal kapasitetini yoxla"""
        active_count = self._get_active_sessions_count()
        max_capacity = self._get_max_capacity()
        
        if active_count >= max_capacity:
            raise ValidationError(
                f'⚠️ Zal doludur!\n'
                f'Aktiv sessiyalar: {active_count}/{max_capacity}\n'
                f'Zəhmət olmasa bir sessiya tamamlanana qədər gözləyin.'
            )
        
        return True

    # ---------- lifecycle ----------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Müştəri ID əsasında name yarat: BS-MUSTERIID
            if vals.get('partner_id'):
                partner_id = vals['partner_id']
                vals['name'] = f"BS-{partner_id}"
            else:
                vals['name'] = 'BS-0'  # Əgər müştəri yoxdursa
            
            # Yaradılma vaxtını set et (növbə üçün lazım)
            if not vals.get('created_at'):
                vals['created_at'] = fields.Datetime.now()
            
            # Start time və end time yaratma zamanı set edilməsin
            # Yalnız sessiya başladılanda set ediləcək
        
        records = super().create(vals_list)
        return records

    def write(self, vals):
        res = super().write(vals)
        # при изменении конца сессии заново разрешаем предупреждение
        if 'end_time' in vals:
            for rec in self.filtered(lambda r: r.state in ('active', 'extended')):
                rec.warn10_sent = False
        return res

    # ---------- helpers / flows ----------
    def _deduct_balance_on_start(self):
        """Sessiya başladıqda balansı azaldır - daxili helper metod"""
        self.ensure_one()
        
        if not self.partner_id:
            raise ValidationError('Zəhmət olmasa müştəri seçin!')

        # Əgər promo_type varsa, balans azaltma
        if self.promo_type:
            _logger.info(f"Sessiya {self.name} tətbiq ({self.promo_type}) ilə başladıldı - balans azaldılmadı")
            return
            
        customer_balance = self.partner_id.badminton_balance or 0.0
        required_hours = float(self.duration_hours)

        if customer_balance < required_hours:
            raise ValidationError(
                f'{self.partner_id.name} müştərisinin kifayət qədər balansı yoxdur! '
                f'Mövcud balans: {customer_balance} saat, Tələb olunan: {required_hours} saat'
            )

        active = self.search([
            ('partner_id', '=', self.partner_id.id),
            ('state', 'in', ['active', 'extended']),
            ('id', '!=', self.id)
        ], limit=1)
        if active:
            raise ValidationError(f'{self.partner_id.name} üçün artıq aktiv sessiya var!')

        new_balance = customer_balance - required_hours
        self.partner_id.badminton_balance = new_balance

        self.env['badminton.balance.history.genclik'].create({
            'partner_id': self.partner_id.id,
            'session_id': self.id,
            'hours_used': required_hours,
            'balance_before': customer_balance,
            'balance_after': new_balance,
            'transaction_type': 'usage',
            'description': f"Sessiya başladıldı: {self.name}"
        })

    def start_session_manual(self):
        """Düymə ilə manual sessiya başlatma"""
        self.ensure_one()
        
        # ÖNCƏ: Zal kapasitetini yoxla
        self._check_capacity()
        
        # Vaxtları set et
        now = fields.Datetime.now()
        end_time = now + timedelta(hours=self.duration_hours)
        
        # Balansı azalt
        self._deduct_balance_on_start()
        
        # Vaxtları və state-i yenilə
        self.write({
            'start_time': now,
            'end_time': end_time,
            'state': 'active',
            'warn10_sent': False,
        })

        customer_balance = self.partner_id.badminton_balance
        
        # Növbə nömrələrini yenilə (compute field olduğu üçün avtomatik olacaq)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': (f'{self.partner_id.name} üçün sessiya başladıldı! '
                            f'Yeni balans: {customer_balance} saat'),
                'type': 'success',
                'sticky': False,
            }
        }

    def start_session_by_qr(self, qr_data):
        try:
            if "ID:" not in qr_data or "NAME:" not in qr_data:
                return {'status': 'error', 'message': 'QR kod formatı səhvdir!'}

            partner_id = int(qr_data.split("ID:")[1].split("-")[0])
            partner = self.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return {'status': 'error', 'message': 'Müştəri tapılmadı!'}

            customer_balance = partner.badminton_balance or 0.0
            required_hours = 1.0
            if customer_balance < required_hours:
                return {'status': 'error',
                        'message': f'{partner.name} müştərisinin kifayət qədər balansı yoxdur! Mövcud balans: {customer_balance} saat'}

            active = self.search([
                ('partner_id', '=', partner_id),
                ('state', 'in', ['active', 'extended'])
            ], limit=1)
            if active:
                return {'status': 'error', 'message': f'{partner.name} üçün artıq aktiv sessiya var!'}

            # Gözləmədə statusunda sessiya yarat (balans azaltma!)
            if customer_balance < required_hours:
                return {'status': 'error',
                        'message': f'{partner.name} müştərisinin kifayət qədər balansı yoxdur! Mövcud balans: {customer_balance} saat'}

            session = self.create({
                'partner_id': partner_id,
                'state': 'draft',  # Gözləmədə statusu
                'qr_scanned': True,
                'duration_hours': 1.0,
            })

            return {'status': 'success',
                    'message': (f'{partner.name} üçün sessiya yaradıldı (Gözləmədə)! '
                                f'Zəhmət olmasa "Başlat" düyməsinə basın.'),
                    'session_id': session.id}
        except Exception as e:
            return {'status': 'error', 'message': f'Xəta baş verdi: {str(e)}'}

    def extend_session(self, additional_hours=1.0):
        for s in self.filtered(lambda r: r.state in ('active', 'extended')):
            current_balance = s.partner_id.badminton_balance or 0.0
            if current_balance < additional_hours:
                raise ValidationError(
                    f'{s.partner_id.name} müştərisinin kifayət qədər balansı yoxdur! '
                    f'Mövcud balans: {current_balance} saat, Uzatmaq üçün tələb olunan: {additional_hours} saat'
                )

            new_balance = current_balance - additional_hours
            s.partner_id.badminton_balance = new_balance

            self.env['badminton.balance.history.genclik'].create({
                'partner_id': s.partner_id.id,
                'session_id': s.id,
                'hours_used': additional_hours,
                'balance_before': current_balance,
                'balance_after': new_balance,
                'transaction_type': 'extension',
                'description': f"Sessiya uzadıldı: {s.name} (+{additional_hours} saat)"
            })

            s.extended_time += additional_hours
            s.end_time = s.end_time + timedelta(hours=additional_hours)
            s.state = 'extended'
            s.notes = (f"Sessiya {additional_hours} saat uzadıldı. "
                       f"Balans: {current_balance} → {new_balance} saat")
            s.warn10_sent = False

    def action_extend_session_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sessiyanı Uzat',
            'res_model': 'badminton.session.extend.wizard.genclik',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_session_id': self.id}
        }

    def complete_session(self):
        for s in self.filtered(lambda r: r.state in ('active', 'extended')):
            s.write({
                'state': 'completed',
                'completion_time': fields.Datetime.now(),
                'notes': (f"Sessiya tamamlandı: {fields.Datetime.now()}. "
                          f"İstifadə edilən saat: {s.duration_hours + s.extended_time}")
            })


    @api.model
    def cron_send_session_warnings(self, warning_minutes=10):
        """
        Крон: уведомляем за ~10 минут до конца через Odoo Bot.
        """
        now = fields.Datetime.now()
        limit_dt = now + timedelta(minutes=warning_minutes)

        sessions = self.search([
            ('state', 'in', ['active', 'extended']),
            ('end_time', '>', now),
            ('end_time', '<=', limit_dt),
            ('warn10_sent', '=', False),
        ])

        if not sessions:
            _logger.info("No sessions found for 10-min warning.")
            return True

        # Находим Odoo Bot и канал 'General'
        bot_user = self.env.ref('base.user_root')
        general_channel = self.env.ref('mail.channel_all_employees')
        
        if not general_channel:
            _logger.warning("General channel not found. Cannot send notification.")
            return False

        for s in sessions:
            mins_left = max(1, int((s.end_time - now).total_seconds() // 60))
            note = f"{s.partner_id.name} üçün sessiyanın bitməsinə {mins_left} dəqiqə qaldı."

            # Отправляем сообщение в чат канала 'General' от имени Odoo Bot
            general_channel.with_user(bot_user).message_post(
                body=note,
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                partner_ids=general_channel.channel_partner_ids.ids,
            )

            s.warn10_sent = True
            _logger.info("Sent Odoo Bot warning for session %s. %s mins left.", s.id, mins_left)

        return True
    # --------- simple queries ----------
    @api.model
    def get_active_sessions(self):
        """Hal-hazırda aktiv olan sessiyaları gətir"""
        active_sessions = self.search([('state', 'in', ['active', 'extended'])])
        data = []
        now = fields.Datetime.now()
        for s in active_sessions:
            remaining = (s.end_time - now) if s.end_time else timedelta()
            data.append({
                'id': s.id,
                'name': s.name,
                'partner_name': s.partner_id.name,
                'start_datetime': fields.Datetime.to_string(s.start_time),
                'end_datetime': fields.Datetime.to_string(s.end_time),
                'minutes_remaining': max(0, int(remaining.total_seconds() // 60)),
                'state': s.state,
            })
        return {'sessions': data}

    @api.model
    def check_expired_sessions(self):
        """По желанию — просто сообщение в чат о просроченных."""
        expired = self.search([
            ('state', 'in', ['active', 'extended']),
            ('end_time', '<=', fields.Datetime.now())
        ])
        for s in expired:
            s.message_post(
                body=f"Diqqət! {s.partner_id.name} müştərisinin vaxtı bitib. Reception ilə əlaqə saxlayın.",
                message_type='notification'
            )

    @api.model
    def _auto_complete_expired_sessions(self):
        """Автодоворот просроченных в completed (если нужно)."""
        now = fields.Datetime.now()
        expired = self.search([('state', 'in', ['active', 'extended']), ('end_time', '<', now)])
        for s in expired:
            s.write({'state': 'completed', 'completion_time': now})
        return True