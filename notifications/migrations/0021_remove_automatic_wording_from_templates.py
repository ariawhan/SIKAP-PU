import re

from django.db import migrations


AUTOMATIC_WORD = re.compile(r"\botomatis\b", flags=re.IGNORECASE)
AUTOMATIC_MESSAGE_LINE = re.compile(
    r"(?im)^[ \t]*Pesan ini dikirim otomatis oleh \{nama_aplikasi\}\.?[ \t]*(?:\r?\n)?",
)
EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def clean_wording(value):
    value = AUTOMATIC_MESSAGE_LINE.sub("", value or "")
    value = AUTOMATIC_WORD.sub("", value)
    value = value.replace("Reminder  ", "Reminder ")
    value = EXTRA_BLANK_LINES.sub("\n\n", value)
    return value.strip()


def remove_automatic_wording(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    fields = ("name", "description", "subject_template", "body_template")
    for template in NotificationTemplate.objects.all().iterator():
        changed_fields = []
        for field_name in fields:
            old_value = getattr(template, field_name)
            new_value = clean_wording(old_value)
            if new_value != old_value:
                setattr(template, field_name, new_value)
                changed_fields.append(field_name)
        if changed_fields:
            template.save(update_fields=changed_fields + ["updated_at"])


class Migration(migrations.Migration):
    dependencies = [("notifications", "0020_enrich_case_notification_templates")]
    operations = [migrations.RunPython(remove_automatic_wording, migrations.RunPython.noop)]
