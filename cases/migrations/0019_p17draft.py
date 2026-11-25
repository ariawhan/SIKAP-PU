from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0018_p16draft_administration_sections"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="P17Draft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveSmallIntegerField(default=1, verbose_name="Permintaan ke")),
                ("letter_number", models.CharField(max_length=120, unique=True, verbose_name="Nomor surat")),
                ("manual_number", models.BooleanField(default=False, verbose_name="Isi nomor surat secara manual")),
                ("letter_date", models.DateField(verbose_name="Tanggal surat")),
                ("letter_nature", models.CharField(default="Biasa", max_length=50, verbose_name="Sifat")),
                ("attachment", models.CharField(default="-", max_length=100, verbose_name="Lampiran")),
                ("subject_html", models.TextField(blank=True, verbose_name="Hal")),
                ("body_html", models.TextField(blank=True, verbose_name="Isi")),
                ("copies_html", models.TextField(blank=True, verbose_name="Tembusan")),
                ("status", models.CharField(choices=[("draft", "Draf")], default="draft", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_p17_drafts", to=settings.AUTH_USER_MODEL, verbose_name="Dibuat oleh")),
                ("last_edited_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="edited_p17_drafts", to=settings.AUTH_USER_MODEL, verbose_name="Terakhir diedit oleh")),
                ("spdp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="p17_drafts", to="cases.spdp", verbose_name="SPDP")),
            ],
            options={
                "verbose_name": "Draf P-17",
                "verbose_name_plural": "Draf P-17",
                "ordering": ("-created_at", "-id"),
                "constraints": [models.UniqueConstraint(fields=("spdp", "sequence"), name="unique_p17_sequence_per_spdp")],
            },
        ),
    ]
