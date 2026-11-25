from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0004_notificationlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationsetting",
            name="whatsapp_last_alert_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Alert WhatsApp terakhir"),
        ),
        migrations.AddField(
            model_name="notificationsetting",
            name="whatsapp_last_alert_status",
            field=models.CharField(blank=True, max_length=30, verbose_name="Status alert WhatsApp terakhir"),
        ),
    ]
