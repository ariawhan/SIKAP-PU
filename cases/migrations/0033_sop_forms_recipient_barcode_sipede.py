from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0032_p17draft_sipede_fields")]

    operations = [
        migrations.AddField(model_name="sopform02draft", name="recipient_html", field=models.TextField(blank=True, verbose_name="Kepada Yth")),
        migrations.AddField(model_name="sopform02draft", name="barcode_image", field=models.ImageField(blank=True, null=True, upload_to="sop-forms/barcodes/%Y/%m/", verbose_name="Barcode/QR")),
        migrations.AddField(model_name="sopform02draft", name="sipede_status", field=models.CharField(choices=[("belum", "Belum diunggah"), ("sudah", "Sudah diunggah")], default="belum", max_length=10)),
        migrations.AddField(model_name="sopform02draft", name="sipede_uploaded_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="sopform03draft", name="recipient_html", field=models.TextField(blank=True, verbose_name="Kepada Yth")),
        migrations.AddField(model_name="sopform03draft", name="barcode_image", field=models.ImageField(blank=True, null=True, upload_to="sop-forms/barcodes/%Y/%m/", verbose_name="Barcode/QR")),
        migrations.AddField(model_name="sopform03draft", name="sipede_status", field=models.CharField(choices=[("belum", "Belum diunggah"), ("sudah", "Sudah diunggah")], default="belum", max_length=10)),
        migrations.AddField(model_name="sopform03draft", name="sipede_uploaded_at", field=models.DateTimeField(blank=True, null=True)),
    ]
