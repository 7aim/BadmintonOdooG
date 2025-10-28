# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class QRScannerWizard(models.TransientModel):
    _name = 'qr.scanner.wizard.genclik'
    _description = 'QR Kod Scanner'

    qr_code_input = fields.Char(string="QR Kod", help="QR scanner cihazından oxunan kodu bura yazın")
    result_message = fields.Text(string="Nəticə", readonly=True)
    session_id = fields.Many2one('badminton.session.genclik', string="Badminton Sessiyası", readonly=True)
    attendance_id = fields.Many2one('sport.attendance.genclik', string="Basketbol İştirakı", readonly=True)
    
    # Müştəri məlumatları
    partner_id = fields.Many2one('res.partner', string="Müştəri", readonly=True)
    partner_image = fields.Binary(string="Müştəri Şəkli", related='partner_id.image_1920', readonly=True)
    
    # Xidmət növü seçimi
    service_type = fields.Selection([
        ('badminton', 'Badminton'),
    ], string="Xidmət Növü", default='badminton', required=True)

    def scan_and_start_session(self):
        """QR kod oxuyub xidmət başlat"""
        if not self.qr_code_input:
            raise ValidationError("❌ QR kod daxil edilməyib! Zəhmət olmasa scanner cihazı ilə QR kodu oxuyun.")
        
        if self.service_type == 'badminton':
            return self._handle_badminton_session()
    
    def _handle_badminton_session(self):
        """Badminton sessiyası üçün QR kod oxuma"""
        try:
            qr_data = self.qr_code_input.strip()
            if "ID-" in qr_data and "NAME-" in qr_data:
                partner_id_str = qr_data.split("ID-")[1].split("-")[0]
                partner_name = qr_data.split("NAME-")[1]
                partner_id = int(partner_id_str)
                
                partner = self.env['res.partner'].browse(partner_id)
                
                if not partner.exists():
                    self.result_message = f"❌ Xəta: ID={partner_id} olan müştəri tapılmadı!\nQR Kod: {qr_data}"
                    return self._return_wizard()
                
                # Müştəri məlumatını set et
                self.partner_id = partner
                
                # ÖNCə AKTIV DƏRS ABUNƏLİYİNİ YOXLA
                lesson_check = self._check_active_lesson(partner)
                if lesson_check['has_lesson']:
                    self.result_message = lesson_check['message']
                    return self._return_wizard()
                
                # Müştərinin badminton balansını yoxla
                current_balance = partner.badminton_balance or 0
                required_hours = 1.0  # Standart 1 saat
                
                if current_balance < required_hours:
                    self.result_message = f"❌ Balans kifayət deyil!\n👤 Müştəri: {partner.name}\n💰 Mövcud balans: {current_balance} saat\n⚠️ Tələb olunan: {required_hours} saat\n\nZəhmət olmasa balansı artırın!"
                    return self._return_wizard()
                
                # Aktiv badminton sessiya var mı yoxla
                active_session = self.env['badminton.session.genclik'].search([
                    ('partner_id', '=', partner_id),
                    ('state', 'in', ['active', 'extended'])
                ], limit=1)
                
                if active_session:
                    self.result_message = f"⚠️ Diqqət: {partner.name} üçün artıq aktiv badminton sessiyası var!\nSessiya: {active_session.name}\nBaşlama vaxtı: {active_session.start_time}"
                    return self._return_wizard()
                
                # Gözləmədə statusunda yeni sessiya yarat (balans hələ azaldılmır)
                session = self.env['badminton.session.genclik'].create({
                    'partner_id': partner_id,
                    'state': 'draft',  # Gözləmədə
                    'qr_scanned': True,
                    'duration_hours': 1.0,
                })
                
                self.result_message = f"✅ SESSİYA YARADILDI (Gözləmədə)!\n👤 Müştəri: {partner.name}\n🎮 Sessiya: {session.name}\n⚠️ Zəhmət olmasa 'Başlat' düyməsinə basın!\n💰 Balans: {current_balance} saat"
                self.session_id = session.id
                
                return self._return_wizard()
                
            else:
                self.result_message = f"❌ QR kod formatı səhvdir!\n\nOxunan kod: '{qr_data}'\n\nDüzgün format: 'ID-123-NAME-Ad Soyad'"
                return self._return_wizard()
                
        except Exception as e:
            self.result_message = f"❌ Badminton xətası: {str(e)}\nOxunan kod: '{self.qr_code_input}'"
            return self._return_wizard()
    
    def _check_active_lesson(self, partner):
        """Müştərinin aktiv dərs abunəliyini və dərs vaxtını yoxla"""
        try:
            # Aktiv dərs abunəliyini tap
            active_lesson = self.env['badminton.lesson.simple.genclik'].search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'active'),
                ('start_date', '<=', fields.Date.today()),
                ('end_date', '>=', fields.Date.today())
            ], limit=1)
            
            if not active_lesson:
                return {'has_lesson': False, 'message': ''}
            
            # İndi dərs vaxtında olub-olmadığını yoxla
            today = fields.Date.today()
            current_time = fields.Datetime.now().time()
            current_weekday = str(today.weekday())  # 0=Bazar ertəsi, 6=Bazar
            current_hour = current_time.hour + current_time.minute / 60.0
            
            # Bu günə aid qrafik var mı?
            matching_schedule = active_lesson.schedule_ids.filtered(
                lambda s: s.day_of_week == current_weekday and s.is_active
            )
            
            if not matching_schedule:
                return {'has_lesson': False, 'message': ''}
            
            # Dərs vaxtında mı?
            for schedule in matching_schedule:
                # 30 dəqiqə əvvəl və 30 dəqiqə sonra QR kodu qəbul et
                start_with_buffer = schedule.start_time - 0.5  # 30 dəq əvvəl
                end_with_buffer = schedule.end_time + 0.5     # 30 dəq sonra
                
                if start_with_buffer <= current_hour <= end_with_buffer:
                    # Həftənin günü adlarını əlavə edək
                    day_names = {
                        '0': 'Bazar ertəsi',
                        '1': 'Çərşənbə axşamı', 
                        '2': 'Çərşənbə',
                        '3': 'Cümə axşamı',
                        '4': 'Cümə',
                        '5': 'Şənbə',
                        '6': 'Bazar'
                    }
                    
                    # Bu gün artıq bu dərsə iştirak var mı yoxla
                    existing_attendance = self.env['badminton.lesson.attendance.simple.genclik'].search([
                        ('lesson_id', '=', active_lesson.id),
                        ('schedule_id', '=', schedule.id),
                        ('attendance_date', '=', today)
                    ], limit=1)
                    
                    if existing_attendance:
                        return {
                            'has_lesson': True,
                            'message': f"⚠️ ARTIQ İŞTİRAK EDİB!\n👤 Müştəri: {partner.name}\n📚 Abunəlik: {active_lesson.name}\n📅 Bu gün artıq bu dərsə iştirak edilib\n⏰ İştirak vaxtı: {existing_attendance.attendance_time.strftime('%H:%M')}"
                        }
                    
                    # Yeni attendance yarat
                    attendance = self.env['badminton.lesson.attendance.simple.genclik'].create({
                        'lesson_id': active_lesson.id,
                        'schedule_id': schedule.id,
                        'attendance_date': today,
                        'attendance_time': fields.Datetime.now(),
                        'qr_scanned': True,
                        'scan_result': f"QR: {partner.name} (ID: {partner.id})"
                    })
                    
                    return {
                        'has_lesson': True,
                        'message': f"✅ DƏRSƏ GİRİŞ UĞURLU!\n👤 Müştəri: {partner.name}\n📚 Abunəlik: {active_lesson.name}\n📅 Dərs günü: {day_names.get(schedule.day_of_week, 'N/A')}\n⏰ Dərs saatı: {int(schedule.start_time):02d}:{int((schedule.start_time % 1) * 60):02d} - {int(schedule.end_time):02d}:{int((schedule.end_time % 1) * 60):02d}\n💡 Balans dəyişmədi (Dərs abunəliyi aktiv)\n📊 Bu aya iştirak: {active_lesson.total_attendances + 1}"
                    }
            
            return {'has_lesson': False, 'message': ''}
            
        except Exception as e:
            return {'has_lesson': False, 'message': f'Dərs yoxlama xətası: {str(e)}'}

    def _return_wizard(self):
        """Wizard pəncərəsini yenilə"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qr.scanner.wizard.genclik',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context
        }

    def open_session(self):
        """Yaradılan sessiyanı aç"""
        if self.session_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'badminton.session.genclik',
                'view_mode': 'form',
                'res_id': self.session_id.id,
                'target': 'current'
            }

    def open_attendance(self):
        """Yaradılan basketbol iştirakını aç"""
        if self.attendance_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sport.attendance',
                'view_mode': 'form',
                'res_id': self.attendance_id.id,
                'target': 'current'
            }

    def scan_new_qr(self):
        """Yeni QR kod scan etmək üçün sahələri təmizlə"""
        self.qr_code_input = False
        self.result_message = False
        self.session_id = False
        self.attendance_id = False
        return self._return_wizard()
