import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import NotificationSetting
from notifications.services import (
    process_due_case_deadline_reminders,
    process_notification_queue,
)


class Command(BaseCommand):
    help = "Menjalankan reminder otomatis tiga hari terakhir untuk setiap tenggat tahapan perkara."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30, help="Jeda pemeriksaan dalam detik.")
        parser.add_argument("--once", action="store_true", help="Periksa sekali lalu berhenti.")

    def handle(self, *args, **options):
        interval = max(10, int(options["interval"]))
        while True:
            setting, _ = NotificationSetting.objects.get_or_create(pk=1)
            now = timezone.localtime()
            if setting.automatic_notification_enabled and now.time().replace(tzinfo=None) >= setting.automatic_notification_time:
                count = process_due_case_deadline_reminders(now.date())
                if count:
                    self.stdout.write(self.style.SUCCESS(f"{count} reminder perkara diproses."))
            sent = process_notification_queue(now)
            if sent:
                self.stdout.write(self.style.SUCCESS(f"{sent} pesan antrean diproses."))
            if options["once"]:
                break
            time.sleep(interval)
