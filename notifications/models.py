from datetime import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .template_defaults import TEMPLATE_DEFINITIONS


class NotificationSetting(models.Model):
    class WhatsAppStatus(models.TextChoices):
        NEED_LOGIN = "need_login", "Perlu login ulang"
        ACTIVE = "active", "Masih aktif"

    telegram_enabled = models.BooleanField("Aktifkan Telegram", default=False)
    telegram_bot_token = models.CharField("Secret key / bot token Telegram", max_length=255, blank=True)
    telegram_default_chat_id = models.CharField("Chat ID bawaan Telegram", max_length=120, blank=True)

    whatsapp_enabled = models.BooleanField("Aktifkan WhatsApp", default=False)
    whatsapp_connection_status = models.CharField(
        "Status koneksi WhatsApp",
        max_length=20,
        choices=WhatsAppStatus.choices,
        default=WhatsAppStatus.NEED_LOGIN,
    )
    whatsapp_last_login_at = models.DateTimeField("Terakhir scan barcode", null=True, blank=True)
    whatsapp_last_alert_status = models.CharField("Status alert WhatsApp terakhir", max_length=30, blank=True)
    whatsapp_last_alert_at = models.DateTimeField("Alert WhatsApp terakhir", null=True, blank=True)

    automatic_notification_enabled = models.BooleanField(
        "Aktifkan notifikasi otomatis", default=True,
    )
    automatic_notification_time = models.TimeField(
        "Jam notifikasi otomatis", default=time(8, 0),
    )
    outbound_message_delay_minutes = models.PositiveSmallIntegerField(
        "Jeda antar pesan (menit)",
        default=2,
        validators=(MinValueValidator(1), MaxValueValidator(60)),
        help_text="Jeda minimum pengiriman antar pesan pada masing-masing channel.",
    )

    updated_at = models.DateTimeField("Terakhir diperbarui", auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Diperbarui oleh",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Setting notifikasi"
        verbose_name_plural = "Setting notifikasi"

    def __str__(self):
        return "Setting notifikasi SIKAP-PU"

    @property
    def telegram_status(self):
        if not self.telegram_enabled:
            return "Nonaktif"
        if self.telegram_bot_token and self.telegram_default_chat_id:
            return "Siap digunakan"
        return "Belum lengkap"

    @property
    def whatsapp_status(self):
        if not self.whatsapp_enabled:
            return "Nonaktif"
        return self.get_whatsapp_connection_status_display()

    @property
    def masked_telegram_token(self):
        return _mask_secret(self.telegram_bot_token)


class NotificationMenuSetting(models.Model):
    class Menu(models.TextChoices):
        SPDP = "spdp", "Data Perkara / SPDP"
        P16 = "p16", "P-16"
        P17 = "p17", "P-17"
        SOP_FORM_02 = "sop02", "SOP Form 2"
        SOP_FORM_03 = "sop03", "SOP Form 3"
        STAGE_ONE = "stage1", "Tahap 1"
        P18 = "p18", "P-18"
        P19 = "p19", "P-19"
        P20 = "p20", "P-20"
        P21 = "p21", "P-21"
        SOP_FORM_07 = "sop07", "SOP Form 7"

    menu_key = models.CharField(
        "Menu / tahapan", max_length=20, choices=Menu.choices, unique=True,
    )
    web_enabled = models.BooleanField("Tampilkan di aplikasi web", default=True)
    whatsapp_enabled = models.BooleanField("Kirim ke WhatsApp", default=True)
    telegram_enabled = models.BooleanField("Kirim ke Telegram", default=True)
    updated_at = models.DateTimeField("Terakhir diperbarui", auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Diperbarui oleh",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Konfigurasi notifikasi per menu"
        verbose_name_plural = "Konfigurasi notifikasi per menu"
        ordering = ("id",)

    def __str__(self):
        return self.get_menu_key_display()

def _mask_secret(value):
    if not value:
        return "Belum diisi"
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}...{value[-4:]}"


class NotificationLog(models.Model):
    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEGRAM = "telegram", "Telegram"

    class Status(models.TextChoices):
        QUEUED = "queued", "Antrean"
        PROCESSING = "processing", "Diproses"
        SENT = "sent", "Terkirim"
        FAILED = "failed", "Gagal"
        CANCELLED = "cancelled", "Dibatalkan"

    channel = models.CharField("Channel", max_length=20, choices=Channel.choices)
    recipient = models.CharField("Tujuan", max_length=160, blank=True)
    recipient_name = models.CharField("Nama penerima", max_length=160, blank=True)
    subject = models.CharField("Judul", max_length=180, blank=True)
    message = models.TextField("Isi pesan", blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.QUEUED)
    provider_message_id = models.CharField("ID pesan provider", max_length=255, blank=True)
    error_message = models.TextField("Pesan error", blank=True)
    context_label = models.CharField("Konteks", max_length=180, blank=True)
    scheduled_at = models.DateTimeField("Dijadwalkan pada", null=True, blank=True, db_index=True)
    attempted_at = models.DateTimeField("Mulai diproses pada", null=True, blank=True)
    created_at = models.DateTimeField("Dibuat", auto_now_add=True)
    sent_at = models.DateTimeField("Terkirim pada", null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Dikirim oleh",
        null=True,
        blank=True,
        related_name="notification_logs",
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Log notifikasi"
        verbose_name_plural = "Log notifikasi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_channel_display()} - {self.get_status_display()}"

    @property
    def preview_message(self):
        text = self.message or self.error_message or "-"
        return text[:120] + ("..." if len(text) > 120 else "")


class WebNotification(models.Model):
    class Kind(models.TextChoices):
        P16_ASSIGNMENT = "p16_assignment", "Penunjukan Jaksa P-16"
        CASE_DEADLINE = "case_deadline", "Reminder batas waktu perkara"
        DOCUMENT_ISSUED = "document_issued", "Dokumen perkara terbit"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Penerima",
        related_name="web_notifications",
        on_delete=models.CASCADE,
    )
    kind = models.CharField("Jenis", max_length=40, choices=Kind.choices, default=Kind.P16_ASSIGNMENT)
    title = models.CharField("Judul", max_length=180)
    message = models.TextField("Pesan")
    target_url = models.CharField("Tautan tujuan", max_length=500, blank=True)
    context_label = models.CharField("Konteks", max_length=180, blank=True)
    spdp = models.ForeignKey(
        "cases.SPDP", verbose_name="Perkara", related_name="deadline_notifications",
        null=True, blank=True, on_delete=models.CASCADE,
    )
    is_read = models.BooleanField("Sudah dibaca", default=False)
    read_at = models.DateTimeField("Dibaca pada", null=True, blank=True)
    created_at = models.DateTimeField("Dibuat", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Dibuat oleh",
        null=True,
        blank=True,
        related_name="created_web_notifications",
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Notifikasi aplikasi"
        verbose_name_plural = "Notifikasi aplikasi"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.recipient}"


class CaseReminderDispatch(models.Model):
    spdp = models.ForeignKey(
        "cases.SPDP", on_delete=models.CASCADE, related_name="reminder_dispatches",
        verbose_name="Perkara",
    )
    stage_key = models.CharField("Tahapan", max_length=20)
    document_id = models.PositiveBigIntegerField("ID dokumen")
    reminder_day = models.PositiveSmallIntegerField("Hari reminder")
    recipient_count = models.PositiveSmallIntegerField("Jumlah penerima", default=0)
    dispatched_at = models.DateTimeField("Dikirim pada", auto_now_add=True)

    class Meta:
        verbose_name = "Pengiriman reminder perkara"
        verbose_name_plural = "Pengiriman reminder perkara"
        ordering = ("-dispatched_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("spdp", "stage_key", "document_id", "reminder_day"),
                name="unique_case_reminder_dispatch",
            ),
        ]

    def __str__(self):
        return f"{self.stage_key} hari ke-{self.reminder_day} - {self.spdp}"


class DocumentIssuedDispatch(models.Model):
    """Catatan idempoten agar satu dokumen terbit hanya dinotifikasi sekali."""

    spdp = models.ForeignKey(
        "cases.SPDP", on_delete=models.CASCADE, related_name="issued_notification_dispatches",
        verbose_name="Perkara",
    )
    stage_key = models.CharField("Tahapan", max_length=20)
    document_id = models.PositiveBigIntegerField("ID dokumen")
    document_number = models.CharField("Nomor dokumen", max_length=180, blank=True)
    recipient_count = models.PositiveSmallIntegerField("Jumlah penerima", default=0)
    dispatched_at = models.DateTimeField("Dikirim pada", auto_now_add=True)

    class Meta:
        verbose_name = "Pengiriman notifikasi dokumen terbit"
        verbose_name_plural = "Pengiriman notifikasi dokumen terbit"
        ordering = ("-dispatched_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("stage_key", "document_id"),
                name="unique_document_issued_dispatch",
            ),
        ]

    def __str__(self):
        return f"{self.stage_key} terbit - {self.document_number or self.document_id}"


class NotificationTemplate(models.Model):
    class Channel(models.TextChoices):
        WEB = "web", "Aplikasi Web"
        WHATSAPP = "whatsapp", "WhatsApp"
        TELEGRAM = "telegram", "Telegram"

    key = models.SlugField("Kode template", max_length=80, unique=True, editable=False)
    name = models.CharField("Nama template", max_length=180, editable=False)
    description = models.CharField("Keterangan", max_length=255, blank=True, editable=False)
    channel = models.CharField("Channel", max_length=20, choices=Channel.choices, editable=False)
    subject_template = models.CharField("Judul notifikasi", max_length=180)
    body_template = models.TextField("Isi pesan")
    updated_at = models.DateTimeField("Terakhir diperbarui", auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Diperbarui oleh",
        null=True,
        blank=True,
        related_name="updated_notification_templates",
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Template notifikasi"
        verbose_name_plural = "Template notifikasi"
        ordering = ("id",)

    def __str__(self):
        return self.name

    @property
    def allowed_variables(self):
        definition = TEMPLATE_DEFINITIONS.get(self.key, {})
        return definition.get("variables", ())

    @property
    def menu_key(self):
        definition = TEMPLATE_DEFINITIONS.get(self.key, {})
        return definition.get("menu_key", "")

    @property
    def is_default(self):
        definition = TEMPLATE_DEFINITIONS.get(self.key, {})
        return (
            self.subject_template == definition.get("subject", "")
            and self.body_template == definition.get("body", "")
        )

    def clean(self):
        definition = TEMPLATE_DEFINITIONS.get(self.key)
        if not definition:
            raise ValidationError({"key": "Jenis template notifikasi tidak dikenal."})
        self.name = definition["name"]
        self.description = definition["description"]
        self.channel = definition["channel"]
