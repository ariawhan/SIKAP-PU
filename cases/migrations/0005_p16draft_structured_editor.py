import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0004_p16draft_content_html_p16draft_last_edited_by"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="p16draft",
            name="manual_number",
            field=models.BooleanField(default=False, verbose_name="Isi nomor surat secara manual"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="consideration_html",
            field=models.TextField(blank=True, verbose_name="Menimbang"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="legal_basis_html",
            field=models.TextField(blank=True, verbose_name="Dasar"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="recipient_html",
            field=models.TextField(blank=True, verbose_name="Kepada"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="instruction_html",
            field=models.TextField(blank=True, verbose_name="Untuk"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="copies_html",
            field=models.TextField(blank=True, verbose_name="Tembusan"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="signatory",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="signed_p16_drafts",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Penanda tangan",
            ),
        ),
    ]
