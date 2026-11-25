from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_cms_address(apps, schema_editor):
    CMSIntegration = apps.get_model("configurations", "CMSIntegration")
    CMSServiceConfiguration = apps.get_model("configurations", "CMSServiceConfiguration")
    integration = CMSIntegration.objects.exclude(base_url="").order_by("-updated_at", "-pk").first()
    if integration:
        CMSServiceConfiguration.objects.create(pk=1, base_url=integration.base_url)


class Migration(migrations.Migration):
    dependencies = [
        ("configurations", "0010_cmsintegration"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CMSServiceConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("base_url", models.URLField(blank=True, verbose_name="Alamat CMS")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Konfigurasi layanan CMS",
            },
        ),
        migrations.RunPython(migrate_cms_address, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="cmsintegration",
            name="base_url",
        ),
    ]
