from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_identity_notification_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="photo",
            field=models.ImageField(blank=True, null=True, upload_to="users/photos/", verbose_name="Foto"),
        ),
        migrations.AddField(
            model_name="user",
            name="photo_position_x",
            field=models.PositiveSmallIntegerField(default=50, verbose_name="Posisi foto X"),
        ),
        migrations.AddField(
            model_name="user",
            name="photo_position_y",
            field=models.PositiveSmallIntegerField(default=50, verbose_name="Posisi foto Y"),
        ),
    ]
