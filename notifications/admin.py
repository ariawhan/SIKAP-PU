from django.contrib import admin

from .models import CaseReminderDispatch, DocumentIssuedDispatch, NotificationLog, NotificationSetting, NotificationTemplate, WebNotification


@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = ("id", "telegram_enabled", "whatsapp_enabled", "updated_at", "updated_by")
    readonly_fields = ("updated_at",)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "scheduled_at", "channel", "recipient", "subject", "status", "triggered_by")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("recipient", "recipient_name", "subject", "message", "error_message")
    readonly_fields = ("created_at", "scheduled_at", "attempted_at", "sent_at")


@admin.register(WebNotification)
class WebNotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "title", "kind", "is_read")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("recipient__username", "recipient__first_name", "title", "message")
    readonly_fields = ("created_at", "read_at")


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "channel", "updated_at", "updated_by")
    list_filter = ("channel",)
    search_fields = ("name", "subject_template", "body_template")
    readonly_fields = ("key", "name", "description", "channel", "updated_at")


@admin.register(CaseReminderDispatch)
class CaseReminderDispatchAdmin(admin.ModelAdmin):
    list_display = ("dispatched_at", "spdp", "stage_key", "reminder_day", "recipient_count")
    list_filter = ("stage_key", "reminder_day", "dispatched_at")
    search_fields = ("spdp__letter_number",)
    readonly_fields = ("dispatched_at",)


@admin.register(DocumentIssuedDispatch)
class DocumentIssuedDispatchAdmin(admin.ModelAdmin):
    list_display = (
        "dispatched_at", "spdp", "stage_key", "document_number", "recipient_count",
    )
    list_filter = ("stage_key", "dispatched_at")
    search_fields = ("spdp__letter_number", "document_number")
    readonly_fields = ("dispatched_at",)
