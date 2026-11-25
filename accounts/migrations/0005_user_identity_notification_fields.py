from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_telegram_chat_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="grade",
            field=models.CharField(blank=True, max_length=10, verbose_name="Golongan"),
        ),
        migrations.AddField(
            model_name="user",
            name="nip",
            field=models.CharField(blank=True, max_length=30, verbose_name="NIP"),
        ),
        migrations.AddField(
            model_name="user",
            name="nrp",
            field=models.CharField(blank=True, max_length=30, verbose_name="NRP"),
        ),
        migrations.AddField(
            model_name="user",
            name="rank",
            field=models.CharField(blank=True, max_length=120, verbose_name="Pangkat"),
        ),
        migrations.AddField(
            model_name="user",
            name="whatsapp_number",
            field=models.CharField(blank=True, max_length=30, verbose_name="Nomor WhatsApp"),
        ),
    ]
