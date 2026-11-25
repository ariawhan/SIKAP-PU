from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0011_notificationmenusetting"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notificationmenusetting",
            name="menu_key",
            field=models.CharField(
                choices=[
                    ("spdp", "Data Perkara / SPDP"),
                    ("p16", "P-16"),
                    ("p17", "P-17"),
                    ("sop02", "SOP Form 02"),
                    ("stage1", "Tahap 1"),
                    ("p19", "P-19"),
                    ("p21", "P-21"),
                ],
                max_length=20,
                unique=True,
                verbose_name="Menu / tahapan",
            ),
        ),
    ]
