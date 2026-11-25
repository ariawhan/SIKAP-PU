from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("configurations", "0012_cmsintegration_session"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentTemplateConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("template_key", models.CharField(max_length=30, unique=True, verbose_name="Menu dokumen")),
                ("sections", models.JSONField(blank=True, default=dict, verbose_name="Template bagian dokumen")),
                ("revision", models.PositiveIntegerField(default=1, verbose_name="Revisi")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_document_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Template generate dokumen",
                "verbose_name_plural": "Template generate dokumen",
                "ordering": ("template_key",),
            },
        ),
    ]
