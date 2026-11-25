from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0026_sopform1bdraft")]

    operations = [
        migrations.AddField(
            model_name="p16draft",
            name="sipede_status",
            field=models.CharField(
                choices=[("belum", "Belum diunggah"), ("sudah", "Sudah diunggah")],
                default="belum",
                max_length=10,
                verbose_name="Status SIPede",
            ),
        ),
        migrations.AddField(
            model_name="p16draft",
            name="sipede_uploaded_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Diunggah ke SIPede"),
        ),
    ]
