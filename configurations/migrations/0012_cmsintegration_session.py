from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("configurations", "0011_cmsserviceconfiguration"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmsintegration",
            name="session_encrypted",
            field=models.TextField(blank=True, verbose_name="Sesi terenkripsi"),
        ),
        migrations.AddField(
            model_name="cmsintegration",
            name="connected_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Terhubung pada"),
        ),
    ]
