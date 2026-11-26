from django.db import migrations


OLD_DEFAULT = 142.1
NEW_DEFAULT = 88


def align_suspect_identity(apps, schema_editor):
    DocumentLayoutConfiguration = apps.get_model(
        "configurations", "DocumentLayoutConfiguration",
    )
    for configuration in DocumentLayoutConfiguration.objects.filter(template_key="p16"):
        settings = dict(configuration.settings or {})
        current = settings.get("suspect_indent_pt", OLD_DEFAULT)
        try:
            uses_old_default = abs(float(current) - OLD_DEFAULT) < 0.001
        except (TypeError, ValueError):
            uses_old_default = False
        if uses_old_default:
            settings["suspect_indent_pt"] = NEW_DEFAULT
            configuration.settings = settings
            configuration.save(update_fields=("settings", "updated_at"))


def restore_suspect_identity(apps, schema_editor):
    DocumentLayoutConfiguration = apps.get_model(
        "configurations", "DocumentLayoutConfiguration",
    )
    for configuration in DocumentLayoutConfiguration.objects.filter(template_key="p16"):
        settings = dict(configuration.settings or {})
        if settings.get("suspect_indent_pt") == NEW_DEFAULT:
            settings["suspect_indent_pt"] = OLD_DEFAULT
            configuration.settings = settings
            configuration.save(update_fields=("settings", "updated_at"))


class Migration(migrations.Migration):
    dependencies = [("configurations", "0013_documenttemplateconfiguration")]
    operations = [
        migrations.RunPython(align_suspect_identity, restore_suspect_identity),
    ]
