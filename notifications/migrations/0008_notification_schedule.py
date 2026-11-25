from datetime import time

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("notifications", "0007_notificationtemplate")]

    operations = [
        migrations.AddField(
            model_name="notificationsetting",
            name="automatic_notification_enabled",
            field=models.BooleanField(default=False, verbose_name="Aktifkan notifikasi otomatis"),
        ),
        migrations.AddField(
            model_name="notificationsetting",
            name="automatic_notification_time",
            field=models.TimeField(default=time(8, 0), verbose_name="Jam notifikasi otomatis"),
        ),
    ]
