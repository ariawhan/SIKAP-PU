from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0027_p16draft_sipede_status")]

    operations = [
        migrations.AddField(
            model_name="casedocumentdraft",
            name="barcode_image",
            field=models.ImageField(blank=True, null=True, upload_to="case-documents/barcodes/%Y/%m/", verbose_name="Barcode/QR"),
        ),
    ]
