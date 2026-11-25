import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0021_sopform02draft_sopform03draft"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="CaseDocumentDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(choices=[("p18", "P-18"), ("p19", "P-19"), ("p20", "P-20"), ("sop07", "SOP Form 7")], max_length=10, verbose_name="Jenis dokumen")),
                ("letter_number", models.CharField(max_length=120, unique=True, verbose_name="Nomor surat")),
                ("manual_number", models.BooleanField(default=False, verbose_name="Isi nomor surat secara manual")),
                ("letter_date", models.DateField(verbose_name="Tanggal surat")),
                ("letter_nature", models.CharField(default="Biasa", max_length=50, verbose_name="Sifat")),
                ("attachment", models.CharField(default="-", max_length=150, verbose_name="Lampiran")),
                ("subject_html", models.TextField(blank=True, verbose_name="Hal")), ("legal_basis_html", models.TextField(blank=True, verbose_name="Dasar")),
                ("body_html", models.TextField(blank=True, verbose_name="Isi")), ("copies_html", models.TextField(blank=True, verbose_name="Tembusan")),
                ("status", models.CharField(choices=[("draft", "Draf")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_case_document_drafts", to=settings.AUTH_USER_MODEL)),
                ("last_edited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="edited_case_document_drafts", to=settings.AUTH_USER_MODEL)),
                ("spdp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="case_document_drafts", to="cases.spdp", verbose_name="SPDP")),
            ], options={"ordering": ("-created_at", "-id"), "verbose_name": "Draf dokumen perkara", "verbose_name_plural": "Draf dokumen perkara"},
        ),
        migrations.AddConstraint(model_name="casedocumentdraft", constraint=models.UniqueConstraint(fields=("spdp", "document_type"), name="unique_case_document_type_per_spdp")),
    ]
