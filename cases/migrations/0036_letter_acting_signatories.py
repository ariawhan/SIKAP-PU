from django.db import migrations, models


ACTING_TYPE_CHOICES = (("plt", "Plt."), ("plh", "Plh."))
MODELS = (
    "p17draft",
    "p21draft",
    "sopform02draft",
    "sopform03draft",
    "casedocumentdraft",
)


class Migration(migrations.Migration):
    dependencies = [("cases", "0035_stageone")]

    operations = [
        operation
        for model_name in MODELS
        for operation in (
            migrations.AddField(
                model_name=model_name,
                name="acting_type",
                field=models.CharField(
                    blank=True,
                    choices=ACTING_TYPE_CHOICES,
                    max_length=3,
                    verbose_name="Status pelaksana",
                ),
            ),
            migrations.AddField(
                model_name=model_name,
                name="acting_name",
                field=models.CharField(
                    blank=True, max_length=150, verbose_name="Nama pejabat pelaksana",
                ),
            ),
            migrations.AddField(
                model_name=model_name,
                name="acting_position",
                field=models.CharField(
                    blank=True, max_length=150, verbose_name="Jabatan/Pangkat pejabat pelaksana",
                ),
            ),
            migrations.AddField(
                model_name=model_name,
                name="acting_nip",
                field=models.CharField(
                    blank=True, max_length=30, verbose_name="NIP pejabat pelaksana",
                ),
            ),
        )
    ]
