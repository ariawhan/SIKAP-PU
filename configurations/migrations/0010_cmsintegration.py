import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("configurations", "0009_sipedeintegration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CMSIntegration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("base_url", models.URLField(verbose_name="Alamat CMS")),
                ("username", models.CharField(max_length=150, verbose_name="Username CMS")),
                ("password_encrypted", models.TextField(verbose_name="Password terenkripsi")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="cms_integration", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Integerasi CMS",
                "verbose_name_plural": "Integerasi CMS",
            },
        ),
    ]
