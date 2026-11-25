import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0020_p21draft"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="SOPForm02Draft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("letter_number", models.CharField(max_length=120, unique=True, verbose_name="Nomor surat")),
                ("manual_number", models.BooleanField(default=False, verbose_name="Isi nomor surat secara manual")),
                ("letter_date", models.DateField(verbose_name="Tanggal surat")),
                ("letter_nature", models.CharField(default="Biasa", max_length=50, verbose_name="Sifat")),
                ("attachment", models.CharField(default="-", max_length=100, verbose_name="Lampiran")),
                ("subject_html", models.TextField(blank=True, verbose_name="Hal")),
                ("body_html", models.TextField(blank=True, verbose_name="Isi")),
                ("copies_html", models.TextField(blank=True, verbose_name="Tembusan")),
                ("status", models.CharField(choices=[("draft", "Draf")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_sop_form_02_drafts", to=settings.AUTH_USER_MODEL)),
                ("last_edited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="edited_sop_form_02_drafts", to=settings.AUTH_USER_MODEL)),
                ("spdp", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="sop_form_02_draft", to="cases.spdp", verbose_name="SPDP")),
            ], options={"ordering": ("-created_at", "-id"), "verbose_name": "Draf SOP Form 02", "verbose_name_plural": "Draf SOP Form 02"},
        ),
        migrations.CreateModel(
            name="SOPForm03Draft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("letter_number", models.CharField(max_length=120, unique=True, verbose_name="Nomor surat")),
                ("manual_number", models.BooleanField(default=False, verbose_name="Isi nomor surat secara manual")),
                ("letter_date", models.DateField(verbose_name="Tanggal surat")),
                ("letter_nature", models.CharField(default="Biasa", max_length=50, verbose_name="Sifat")),
                ("attachment", models.CharField(default="-", max_length=100, verbose_name="Lampiran")),
                ("subject_html", models.TextField(blank=True, verbose_name="Hal")),
                ("body_html", models.TextField(blank=True, verbose_name="Isi")),
                ("copies_html", models.TextField(blank=True, verbose_name="Tembusan")),
                ("status", models.CharField(choices=[("draft", "Draf")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_sop_form_03_drafts", to=settings.AUTH_USER_MODEL)),
                ("last_edited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="edited_sop_form_03_drafts", to=settings.AUTH_USER_MODEL)),
                ("spdp", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="sop_form_03_draft", to="cases.spdp", verbose_name="SPDP")),
            ], options={"ordering": ("-created_at", "-id"), "verbose_name": "Draf SOP Form 03", "verbose_name_plural": "Draf SOP Form 03"},
        ),
    ]
