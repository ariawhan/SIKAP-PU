from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0016_p16assignment_appointed_prosecutors"),
    ]

    operations = [
        migrations.AddField(
            model_name="p16draft",
            name="offense_summary_html",
            field=models.TextField(blank=True, verbose_name="Uraian tindak pidana"),
        ),
    ]
