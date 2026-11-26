from django.db import migrations


TEMPLATE_KEYS = (
    "p18_investigator_issued_whatsapp",
    "p18_investigator_issued_telegram",
    "p19_investigator_issued_whatsapp",
    "p19_investigator_issued_telegram",
)


def create_templates(apps, schema_editor):
    from notifications.template_defaults import TEMPLATE_DEFINITIONS

    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for key in TEMPLATE_KEYS:
        definition = TEMPLATE_DEFINITIONS[key]
        NotificationTemplate.objects.get_or_create(
            key=key,
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "channel": definition["channel"],
                "subject_template": definition["subject"],
                "body_template": definition["body"],
            },
        )


def remove_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(key__in=TEMPLATE_KEYS).delete()


class Migration(migrations.Migration):
    dependencies = [("notifications", "0023_investigator_telegram_templates")]
    operations = [migrations.RunPython(create_templates, remove_templates)]
