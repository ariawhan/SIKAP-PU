from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0028_casedocumentdraft_barcode_image")]

    operations = [
        migrations.AddField(
            model_name="p16draft",
            name="acting_type",
            field=models.CharField(blank=True, choices=[("plt", "Plt."), ("plh", "Plh.")], max_length=3, verbose_name="Status pelaksana"),
        ),
    ]
