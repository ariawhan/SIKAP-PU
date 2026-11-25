import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0025_coordinationminutesdraft"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SOPForm1BDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_date", models.DateField(default=django.utils.timezone.localdate, verbose_name="Tanggal laporan")),
                ("recipient", models.CharField(max_length=300, verbose_name="Kepada Yth.")),
                ("sender", models.TextField(verbose_name="Dari")),
                ("attachment", models.CharField(default="1 (satu) berkas", max_length=100, verbose_name="Lampiran")),
                ("subject", models.TextField(verbose_name="Perihal")),
                ("legal_basis_html", models.TextField(blank=True, verbose_name="Dasar")),
                ("facts_html", models.TextField(blank=True, verbose_name="Fakta dan data")),
                ("legal_analysis_html", models.TextField(blank=True, verbose_name="Analisis yuridis")),
                ("conclusion_html", models.TextField(blank=True, verbose_name="Kesimpulan dan saran")),
                ("closing", models.TextField(default="Demikian untuk menjadi periksa dan mohon petunjuk.", verbose_name="Penutup")),
                ("prosecutor_name", models.CharField(blank=True, max_length=180, verbose_name="Nama Penuntut Umum")),
                ("prosecutor_rank", models.CharField(blank=True, max_length=120, verbose_name="Pangkat Penuntut Umum")),
                ("prosecutor_nip", models.CharField(blank=True, max_length=30, verbose_name="NIP Penuntut Umum")),
                ("kasi_opinion_html", models.TextField(blank=True, verbose_name="Pendapat Kasipidum")),
                ("leader_instruction_html", models.TextField(blank=True, verbose_name="Petunjuk Kajari")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_edited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="edited_sop_form_1b_drafts", to=settings.AUTH_USER_MODEL, verbose_name="Terakhir diedit oleh")),
                ("p17_draft", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="sop_form_1b", to="cases.p17draft", verbose_name="Draf P-17")),
            ],
            options={
                "verbose_name": "Draf SOP Form-1B",
                "verbose_name_plural": "Draf SOP Form-1B",
            },
        ),
    ]
