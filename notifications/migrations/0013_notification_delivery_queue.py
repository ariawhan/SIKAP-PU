from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0012_alter_notificationmenusetting_menu_key"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationlog",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Antrean"),
                    ("processing", "Diproses"),
                    ("sent", "Terkirim"),
                    ("failed", "Gagal"),
                ],
                default="queued",
                max_length=20,
                verbose_name="Status",
            ),
        ),
        migrations.AddField(
            model_name="notificationlog",
            name="scheduled_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Dijadwalkan pada",
            ),
        ),
        migrations.AddField(
            model_name="notificationlog",
            name="attempted_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Mulai diproses pada",
            ),
        ),
    ]
