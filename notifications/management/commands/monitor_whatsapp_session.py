import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import NotificationSetting
from notifications.services import (
    log_whatsapp_session_telegram_alert,
    send_whatsapp_logout_telegram_alert,
    send_whatsapp_recovered_telegram_alert,
)
from notifications.views import _gateway_request


class Command(BaseCommand):
    help = "Memantau status session WhatsApp Gateway dan mengirim alert Telegram saat logout otomatis."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=300, help="Jeda cek status dalam detik. Default 300 detik.")
        parser.add_argument("--reminder", type=int, default=3600, help="Jeda pengingat ulang dalam detik. Default 3600 detik.")
        parser.add_argument("--once", action="store_true", help="Cek sekali lalu keluar. Dipakai untuk test/diagnostik.")

    def handle(self, *args, **options):
        interval = max(30, int(options["interval"]))
        reminder_seconds = max(300, int(options["reminder"]))
        self.stdout.write(self.style.SUCCESS(f"[OK] Monitor WhatsApp berjalan. Cek status setiap {interval} detik."))

        while True:
            self._check_once(reminder_seconds)
            if options["once"]:
                return
            time.sleep(interval)

    def _check_once(self, reminder_seconds):
        setting, _ = NotificationSetting.objects.get_or_create(pk=1)
        if not setting.whatsapp_enabled:
            self.stdout.write("[INFO] WhatsApp nonaktif di setting. Monitor melewati cek.")
            return

        payload, status_code = _gateway_request("GET", f"/sessions/{settings.WA_GATEWAY_SESSION}/status")
        current_status = _normalize_gateway_status(payload)
        previous_status = setting.whatsapp_connection_status
        now = timezone.now()

        setting.whatsapp_connection_status = (
            NotificationSetting.WhatsAppStatus.ACTIVE
            if current_status == NotificationSetting.WhatsAppStatus.ACTIVE
            else NotificationSetting.WhatsAppStatus.NEED_LOGIN
        )
        if current_status == NotificationSetting.WhatsAppStatus.ACTIVE and not setting.whatsapp_last_login_at:
            setting.whatsapp_last_login_at = now

        should_alert_logout = current_status != NotificationSetting.WhatsAppStatus.ACTIVE and (
            previous_status == NotificationSetting.WhatsAppStatus.ACTIVE
            or setting.whatsapp_last_alert_status != current_status
            or _alert_cooldown_passed(setting.whatsapp_last_alert_at, now, reminder_seconds)
        )
        should_alert_recovered = (
            current_status == NotificationSetting.WhatsAppStatus.ACTIVE
            and previous_status != NotificationSetting.WhatsAppStatus.ACTIVE
            and setting.whatsapp_last_alert_status
        )

        if should_alert_logout:
            alert_payload, _ = send_whatsapp_logout_telegram_alert(reason="monitor")
            log_whatsapp_session_telegram_alert(alert_payload, "WhatsApp Gateway Logout Otomatis")
            setting.whatsapp_last_alert_status = current_status
            setting.whatsapp_last_alert_at = now
            self.stdout.write("[ALERT] WhatsApp perlu login ulang. Alert Telegram diproses.")
        elif should_alert_recovered:
            alert_payload, _ = send_whatsapp_recovered_telegram_alert()
            log_whatsapp_session_telegram_alert(alert_payload, "WhatsApp Gateway Aktif Kembali")
            setting.whatsapp_last_alert_status = ""
            setting.whatsapp_last_alert_at = now
            self.stdout.write("[OK] WhatsApp aktif kembali. Info Telegram diproses.")
        else:
            self.stdout.write(f"[INFO] Status WhatsApp: {current_status}. Tidak ada alert baru.")

        setting.save(update_fields=[
            "whatsapp_connection_status",
            "whatsapp_last_login_at",
            "whatsapp_last_alert_status",
            "whatsapp_last_alert_at",
            "updated_at",
        ])


def _normalize_gateway_status(payload):
    status = (payload or {}).get("status")
    if status == "active":
        return NotificationSetting.WhatsAppStatus.ACTIVE
    return NotificationSetting.WhatsAppStatus.NEED_LOGIN


def _alert_cooldown_passed(last_alert_at, now, reminder_seconds):
    if not last_alert_at:
        return True
    return (now - last_alert_at).total_seconds() >= reminder_seconds
