import asyncio

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from notifications.models import NotificationLog, NotificationSetting


class Command(BaseCommand):
    help = "Menjalankan polling bot Telegram SIKAP-PU untuk membalas /start otomatis."

    def handle(self, *args, **options):
        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, ContextTypes
        except ImportError:
            self.stderr.write(self.style.ERROR("Library python-telegram-bot belum terpasang. Jalankan pip install -r requirements.txt."))
            return

        async def get_setting():
            return await sync_to_async(NotificationSetting.objects.get_or_create)(pk=1)

        async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
            chat = update.effective_chat
            message = update.effective_message
            if not chat or not message:
                return

            chat_id = str(chat.id)
            chat_name = " ".join(filter(None, [getattr(chat, "first_name", ""), getattr(chat, "last_name", "")]))
            chat_name = chat_name or getattr(chat, "username", "") or getattr(chat, "title", "") or chat_id
            linked_user = await _link_user_from_start_args(context.args, chat_id)

            if linked_user:
                text = "\n".join([
                    "Halo, Telegram Anda sudah terhubung ke akun SIKAP-PU.",
                    "",
                    f"Nama: {linked_user.display_name}",
                    f"Chat ID Anda: {chat_id}",
                    "",
                    "Notifikasi Telegram dapat dikirim ke akun ini.",
                ])
                recipient_name = linked_user.display_name
            else:
                text = "\n".join([
                    "Halo, ini Chat ID Telegram Anda:",
                    "",
                    chat_id,
                    "",
                    "Masukkan Chat ID ini di data pengguna SIKAP-PU agar notifikasi dapat dikirim otomatis.",
                ])
                recipient_name = chat_name

            sent_message = await message.reply_text(text)
            await _log_start_reply(chat_id, recipient_name, text, sent_message.message_id)

        while True:
            setting, _ = asyncio.run(get_setting())
            if setting.telegram_enabled and setting.telegram_bot_token:
                break
            self.stdout.write("[INFO] Telegram belum aktif atau token belum diisi. Menunggu setting Telegram...")
            import time
            time.sleep(10)

        self.stdout.write(self.style.SUCCESS("[OK] Bot Telegram SIKAP-PU berjalan. Kirim /start ke bot untuk melihat Chat ID."))
        asyncio.set_event_loop(asyncio.new_event_loop())
        application = Application.builder().token(setting.telegram_bot_token).build()
        application.add_handler(CommandHandler("start", start_command))
        application.run_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES)


@sync_to_async
def _link_user_from_start_args(args, chat_id):
    if not args:
        return None
    key = str(args[0]).strip()
    if not key:
        return None

    user = (
        User.objects.filter(username__iexact=key, is_active=True).first()
        or User.objects.filter(email__iexact=key, is_active=True).first()
    )
    if not user:
        return None
    user.telegram_chat_id = chat_id
    user.save(update_fields=["telegram_chat_id"])
    return user


@sync_to_async
def _log_start_reply(chat_id, recipient_name, text, message_id):
    NotificationLog.objects.create(
        channel=NotificationLog.Channel.TELEGRAM,
        recipient=chat_id,
        recipient_name=recipient_name,
        subject="Balasan /start Telegram",
        message=text,
        status=NotificationLog.Status.SENT,
        provider_message_id=str(message_id or ""),
        context_label="Telegram Bot",
        sent_at=timezone.now(),
    )
