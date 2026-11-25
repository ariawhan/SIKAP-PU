from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0029_p16draft_acting_type")]

    operations = [
        migrations.AddField(model_name="p16draft", name="acting_name", field=models.CharField(blank=True, max_length=150, verbose_name="Nama pejabat pelaksana")),
        migrations.AddField(model_name="p16draft", name="acting_position", field=models.CharField(blank=True, max_length=150, verbose_name="Jabatan/Pangkat pejabat pelaksana")),
        migrations.AddField(model_name="p16draft", name="acting_nip", field=models.CharField(blank=True, max_length=30, verbose_name="NIP pejabat pelaksana")),
    ]
