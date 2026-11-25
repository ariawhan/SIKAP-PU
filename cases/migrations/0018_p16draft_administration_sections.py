from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0017_p16draft_offense_summary_html"),
    ]

    operations = [
        migrations.AddField(
            model_name="p16draft",
            name="administration_legal_basis_html",
            field=models.TextField(blank=True, verbose_name="Dasar petugas administrasi"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="administration_consideration_html",
            field=models.TextField(blank=True, verbose_name="Pertimbangan petugas administrasi"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="administration_instruction_html",
            field=models.TextField(blank=True, verbose_name="Untuk petugas administrasi"),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="administration_copies_html",
            field=models.TextField(blank=True, verbose_name="Tembusan petugas administrasi"),
        ),
    ]
