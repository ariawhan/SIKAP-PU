from django.db import migrations


def add_kasubsi_role(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.update_or_create(
        code="kasubsi_prapenuntutan",
        defaults={"name": "Kepala Sub Seksi Pra Penuntutan", "sort_order": 35},
    )


def remove_kasubsi_role(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code="kasubsi_prapenuntutan").delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0006_user_photo_user_photo_position_x_and_more")]
    operations = [migrations.RunPython(add_kasubsi_role, remove_kasubsi_role)]
