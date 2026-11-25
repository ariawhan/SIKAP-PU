from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("configurations", "0008_documentlayoutconfiguration")]

    operations = [
        migrations.CreateModel(
            name="SipedeIntegration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=150, verbose_name="Username SIPede")),
                ("password_encrypted", models.TextField(verbose_name="Password terenkripsi")),
                ("session_encrypted", models.TextField(blank=True, verbose_name="Sesi terenkripsi")),
                ("connected_at", models.DateTimeField(blank=True, null=True, verbose_name="Terhubung pada")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="sipede_integration", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Integrasi SIPede", "verbose_name_plural": "Integrasi SIPede"},
        ),
    ]
