from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_role_alter_user_options_remove_user_role_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="telegram_chat_id",
            field=models.CharField(blank=True, max_length=120, verbose_name="Chat ID Telegram"),
        ),
    ]
