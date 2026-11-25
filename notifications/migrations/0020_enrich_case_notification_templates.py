from django.db import migrations


CASE_DETAIL_BLOCK = (
    "\n\nData penanganan perkara:\n"
    "Pelaku / terlapor    : {daftar_pelaku}\n"
    "Jaksa yang menangani : {daftar_jaksa}\n"
    "Petugas administrasi : {daftar_pegawai}"
)


def enrich_case_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    for template in NotificationTemplate.objects.all().iterator():
        key = template.key
        is_case_template = (
            key.startswith("p16_assignment_")
            or "_deadline_" in key
            or "_issued_" in key
        )
        if not is_case_template or "{daftar_pelaku}" in template.body_template:
            continue
        template.body_template = template.body_template.rstrip() + CASE_DETAIL_BLOCK
        template.save(update_fields=("body_template", "updated_at"))


class Migration(migrations.Migration):
    dependencies = [("notifications", "0019_alter_notificationmenusetting_menu_key_and_more")]
    operations = [migrations.RunPython(enrich_case_templates, migrations.RunPython.noop)]
