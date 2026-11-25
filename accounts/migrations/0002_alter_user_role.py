from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("super_admin", "Super Admin"),
                    ("jaksa", "Jaksa"),
                    ("pegawai", "Pegawai"),
                ],
                default="admin",
                max_length=20,
            ),
        ),
    ]
