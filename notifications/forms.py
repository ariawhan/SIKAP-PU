import string

from django import forms

from .models import NotificationSetting, NotificationTemplate


class NotificationSettingForm(forms.ModelForm):
    class Meta:
        model = NotificationSetting
        fields = (
            "telegram_enabled", "telegram_bot_token", "telegram_default_chat_id",
            "whatsapp_enabled",
        )
        widgets = {
            "telegram_bot_token": forms.PasswordInput(render_value=True, attrs={"autocomplete": "off"}),
        }


class TelegramNotificationSettingForm(forms.ModelForm):
    class Meta:
        model = NotificationSetting
        fields = ("telegram_enabled", "telegram_bot_token", "telegram_default_chat_id")
        widgets = {
            "telegram_bot_token": forms.PasswordInput(render_value=True, attrs={"autocomplete": "off"}),
        }


class WhatsAppNotificationSettingForm(forms.ModelForm):
    class Meta:
        model = NotificationSetting
        fields = ("whatsapp_enabled",)


class AutomaticNotificationSettingForm(forms.ModelForm):
    class Meta:
        model = NotificationSetting
        fields = (
            "automatic_notification_enabled",
            "automatic_notification_time",
            "outbound_message_delay_minutes",
        )
        widgets = {
            "automatic_notification_time": forms.TimeInput(
                attrs={"type": "time", "step": "60"}, format="%H:%M",
            ),
            "outbound_message_delay_minutes": forms.NumberInput(
                attrs={"min": "1", "max": "60", "step": "1"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["automatic_notification_time"].input_formats = ["%H:%M"]


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ("subject_template", "body_template")
        widgets = {
            "subject_template": forms.TextInput(attrs={"autocomplete": "off"}),
            "body_template": forms.Textarea(attrs={"rows": 16, "spellcheck": "true"}),
        }

    def clean(self):
        cleaned = super().clean()
        allowed = set(self.instance.allowed_variables)
        for field_name in ("subject_template", "body_template"):
            value = cleaned.get(field_name, "")
            try:
                variables = {
                    name for _, name, _, _ in string.Formatter().parse(value)
                    if name
                }
            except ValueError:
                self.add_error(field_name, "Format kurung kurawal tidak valid.")
                continue
            invalid = variables - allowed
            if invalid:
                self.add_error(
                    field_name,
                    "Variabel tidak tersedia: " + ", ".join(f"{{{item}}}" for item in sorted(invalid)),
                )
        return cleaned
