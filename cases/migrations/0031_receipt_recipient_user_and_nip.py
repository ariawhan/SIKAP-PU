import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cases", "0030_p16draft_acting_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="receipt",
            name="recipient_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="spdp_receipts",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Nama penerima",
            ),
        ),
        migrations.AddField(
            model_name="receipt",
            name="recipient_nip",
            field=models.CharField(blank=True, max_length=30, verbose_name="NIP penerima"),
        ),
    ]
