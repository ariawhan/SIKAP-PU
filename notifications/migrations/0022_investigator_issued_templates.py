from django.db import migrations


INVESTIGATOR_TEMPLATE_KEYS = (
    "p17_investigator_issued_whatsapp",
    "sop02_investigator_issued_whatsapp",
    "sop03_investigator_issued_whatsapp",
    "p21_investigator_issued_whatsapp",
)


def create_investigator_templates(apps, schema_editor):
    from notifications.template_defaults import TEMPLATE_DEFINITIONS

    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for key in INVESTIGATOR_TEMPLATE_KEYS:
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


def remove_investigator_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    NotificationTemplate.objects.filter(key__in=INVESTIGATOR_TEMPLATE_KEYS).delete()


class Migration(migrations.Migration):
    dependencies = [("notifications", "0021_remove_automatic_wording_from_templates")]
    operations = [
        migrations.RunPython(create_investigator_templates, remove_investigator_templates),
    ]
