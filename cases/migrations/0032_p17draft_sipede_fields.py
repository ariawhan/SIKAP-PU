from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cases", "0031_receipt_recipient_user_and_nip")]
    operations = [
        migrations.AddField(model_name="p17draft", name="sipede_status", field=models.CharField(choices=[("belum", "Belum diunggah"), ("sudah", "Sudah diunggah")], default="belum", max_length=10)),
        migrations.AddField(model_name="p17draft", name="sipede_uploaded_at", field=models.DateTimeField(blank=True, null=True)),
    ]
