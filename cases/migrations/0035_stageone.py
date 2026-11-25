import cases.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0034_document_recipients_barcode_sipede"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StageOne",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("case_file_number", models.CharField(max_length=200, verbose_name="Nomor berkas perkara")),
                ("cover_letter_number", models.CharField(max_length=200, verbose_name="Nomor surat pengantar")),
                ("laws_and_articles", models.TextField(verbose_name="Undang-undang dan pasal dalam berkas perkara")),
                ("cover_letter_document", models.FileField(upload_to="stage-one/cover-letters/%Y/%m/", validators=[cases.models.validate_stage_one_pdf], verbose_name="Surat pengantar")),
                ("completed_at", models.DateTimeField(auto_now_add=True, verbose_name="Tahap 1 diselesaikan")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_stage_one_records", to=settings.AUTH_USER_MODEL, verbose_name="Dibuat oleh")),
                ("spdp", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="stage_one", to="cases.spdp", verbose_name="Perkara")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_stage_one_records", to=settings.AUTH_USER_MODEL, verbose_name="Diperbarui oleh")),
            ],
            options={"verbose_name": "Tahap 1", "verbose_name_plural": "Tahap 1", "ordering": ("-completed_at", "-id")},
        ),
    ]
