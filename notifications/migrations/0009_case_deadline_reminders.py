from django.db import migrations, models
import django.db.models.deletion


def enable_automatic_reminders(apps, schema_editor):
    NotificationSetting = apps.get_model("notifications", "NotificationSetting")
    NotificationSetting.objects.update_or_create(
        pk=1, defaults={"automatic_notification_enabled": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0035_stageone"),
        ("notifications", "0008_notification_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="webnotification",
            name="spdp",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="deadline_notifications", to="cases.spdp", verbose_name="Perkara"),
        ),
        migrations.AlterField(
            model_name="webnotification",
            name="kind",
            field=models.CharField(choices=[("p16_assignment", "Penunjukan Jaksa P-16"), ("case_deadline", "Reminder batas waktu perkara")], default="p16_assignment", max_length=40, verbose_name="Jenis"),
        ),
        migrations.CreateModel(
            name="CaseReminderDispatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage_key", models.CharField(max_length=20, verbose_name="Tahapan")),
                ("document_id", models.PositiveBigIntegerField(verbose_name="ID dokumen")),
                ("reminder_day", models.PositiveSmallIntegerField(verbose_name="Hari reminder")),
                ("recipient_count", models.PositiveSmallIntegerField(default=0, verbose_name="Jumlah penerima")),
                ("dispatched_at", models.DateTimeField(auto_now_add=True, verbose_name="Dikirim pada")),
                ("spdp", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reminder_dispatches", to="cases.spdp", verbose_name="Perkara")),
            ],
            options={
                "verbose_name": "Pengiriman reminder perkara",
                "verbose_name_plural": "Pengiriman reminder perkara",
                "ordering": ("-dispatched_at",),
                "constraints": [models.UniqueConstraint(fields=("spdp", "stage_key", "document_id", "reminder_day"), name="unique_case_reminder_dispatch")],
            },
        ),
        migrations.AlterField(
            model_name="notificationsetting",
            name="automatic_notification_enabled",
            field=models.BooleanField(default=True, verbose_name="Aktifkan notifikasi otomatis"),
        ),
        migrations.RunPython(enable_automatic_reminders, migrations.RunPython.noop),
    ]
