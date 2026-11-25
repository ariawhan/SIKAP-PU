from django.conf import settings
from django.db import migrations, models


def copy_existing_prosecutors(apps, schema_editor):
    P16Assignment = apps.get_model("cases", "P16Assignment")
    for assignment in P16Assignment.objects.all().iterator():
        assignment.appointed_prosecutors.set(assignment.prosecutors.all())


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0015_p16draft_barcode_image"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="p16assignment",
            name="appointed_prosecutors",
            field=models.ManyToManyField(
                blank=True,
                related_name="p16_as_appointed_prosecutor",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Jaksa yang ditunjuk awal",
            ),
        ),
        migrations.RunPython(copy_existing_prosecutors, migrations.RunPython.noop),
    ]
