import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def add_initial_letter_numbers(apps, schema_editor):
    letter_number_code = apps.get_model("configurations", "LetterNumberCode")
    for directorate, code in (
        ("Dir A", "Eoh"),
        ("Dir B", "Enz"),
        ("Dir C", "Etl"),
        ("Dir D dan E", "Eku"),
    ):
        letter_number_code.objects.get_or_create(
            directorate=directorate,
            defaults={"code": code},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("configurations", "0003_institutionconfiguration_leader_rank"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LetterNumberCode",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("directorate", models.CharField(max_length=80, unique=True, verbose_name="Direktorat")),
                ("code", models.CharField(max_length=30, unique=True, verbose_name="Kode surat")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Kode nomor surat",
                "verbose_name_plural": "Kode nomor surat",
                "ordering": ("id",),
            },
        ),
        migrations.RunPython(add_initial_letter_numbers, migrations.RunPython.noop),
    ]
