from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

import json
from urllib import error, request as urlrequest

from dashboard.decorators import super_admin_required
from dashboard.pagination import paginate_queryset

from .forms import (
    AutomaticNotificationSettingForm,
    NotificationSettingForm,
    NotificationTemplateForm,
    TelegramNotificationSettingForm,
    WhatsAppNotificationSettingForm,
)
from .models import NotificationLog, NotificationMenuSetting, NotificationSetting, NotificationTemplate, WebNotification
from .services import (
    ensure_notification_menu_settings,
    ensure_notification_templates,
    log_whatsapp_session_telegram_alert,
    send_telegram_message,
    send_whatsapp_logout_telegram_alert,
)
from .template_defaults import TEMPLATE_DEFINITIONS


@login_required
def mark_web_notifications_read(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Metode tidak diizinkan."}, status=405)
    updated = WebNotification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )
    return JsonResponse({"ok": True, "updated": updated})


@login_required
@super_admin_required
def settings_view(request):
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    telegram_form = TelegramNotificationSettingForm(instance=setting, prefix="telegram")
    whatsapp_form = WhatsAppNotificationSettingForm(instance=setting, prefix="whatsapp")
    automatic_form = AutomaticNotificationSettingForm(instance=setting, prefix="automatic")
    User = get_user_model()

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "cancel_queue":
            cancelled = NotificationLog.objects.filter(
                status=NotificationLog.Status.QUEUED,
            ).update(
                status=NotificationLog.Status.CANCELLED,
                scheduled_at=None,
                error_message=f"Antrean dibatalkan oleh {request.user.display_name}.",
            )
            if cancelled:
                messages.success(request, f"{cancelled} pesan dalam antrean berhasil dibatalkan.")
            else:
                messages.info(request, "Tidak ada pesan yang masih menunggu dalam antrean.")
            return redirect("notifications:index")
        elif action == "save_automatic":
            automatic_form = AutomaticNotificationSettingForm(
                request.POST, instance=setting, prefix="automatic",
            )
            if _save_setting_form(automatic_form, request):
                messages.success(request, "Jam notifikasi otomatis berhasil disimpan.")
                return redirect("notifications:index")
        elif action == "save_telegram":
            telegram_form = TelegramNotificationSettingForm(request.POST, instance=setting, prefix="telegram")
            if _save_setting_form(telegram_form, request):
                messages.success(request, "Setting Telegram berhasil disimpan.")
                return redirect("notifications:index")
        elif action == "save_whatsapp":
            whatsapp_form = WhatsAppNotificationSettingForm(request.POST, instance=setting, prefix="whatsapp")
            if _save_setting_form(whatsapp_form, request):
                messages.success(request, "Setting WhatsApp berhasil disimpan.")
                return redirect("notifications:index")
        else:
            form = NotificationSettingForm(request.POST, instance=setting)
            if _save_setting_form(form, request):
                messages.success(request, "Setting notifikasi berhasil disimpan.")
                return redirect("notifications:index")

    page_obj, logs = paginate_queryset(request, NotificationLog.objects.select_related("triggered_by"), per_page=10)
    return render(request, "notifications/settings.html", {
        "telegram_form": telegram_form,
        "whatsapp_form": whatsapp_form,
        "automatic_form": automatic_form,
        "setting": setting,
        "wa_session": settings.WA_GATEWAY_SESSION,
        "logs": logs,
        "page_obj": page_obj,
        "stats": _notification_stats(),
        "telegram_users": User.objects.filter(is_active=True).order_by("first_name", "username"),
    })


@login_required
@super_admin_required
def menu_settings_view(request):
    # Alamat lama tetap berfungsi, tetapi seluruh konfigurasi kini dipusatkan
    # pada editor masing-masing template.
    return redirect("notifications:template_settings")


@login_required
@super_admin_required
def template_settings_view(request):
    templates = ensure_notification_templates()
    menu_settings = {
        item.menu_key: item
        for item in ensure_notification_menu_settings()
    }
    selected_key = request.POST.get("template_key") or request.GET.get("edit", "")
    selected_template = next((item for item in templates if item.key == selected_key), None)
    template_form = NotificationTemplateForm(instance=selected_template) if selected_template else None
    selected_menu_setting = (
        menu_settings.get(selected_template.menu_key) if selected_template else None
    )

    if request.method == "POST":
        if not selected_template:
            messages.error(request, "Template notifikasi tidak ditemukan.")
            return redirect("notifications:template_settings")

        if request.POST.get("action") == "reset_template":
            definition = TEMPLATE_DEFINITIONS[selected_template.key]
            selected_template.subject_template = definition["subject"]
            selected_template.body_template = definition["body"]
            selected_template.updated_by = request.user
            selected_template.full_clean()
            selected_template.save()
            messages.success(request, f"Template {selected_template.name} dikembalikan ke bawaan sistem.")
            return redirect(f'{reverse("notifications:template_settings")}?edit={selected_template.key}')

        template_form = NotificationTemplateForm(request.POST, instance=selected_template)
        if template_form.is_valid():
            template = template_form.save(commit=False)
            template.updated_by = request.user
            template.full_clean()
            template.save()
            _save_template_menu_channels(request, selected_menu_setting, template)
            messages.success(request, f"Template {template.name} berhasil diperbarui.")
            return redirect(f'{reverse("notifications:template_settings")}?edit={template.key}')
        messages.error(request, "Template belum dapat disimpan. Periksa kembali isi pesan.")

    return render(request, "notifications/template_settings.html", {
        "notification_templates": templates,
        "selected_template": selected_template,
        "selected_menu_setting": selected_menu_setting,
        "template_form": template_form,
    })


def _save_template_menu_channels(request, menu_setting, template):
    if not menu_setting:
        return
    update_fields = ["updated_by", "updated_at"]
    if template.channel == NotificationTemplate.Channel.WEB:
        menu_setting.web_enabled = "menu_web_enabled" in request.POST
        update_fields.append("web_enabled")
    else:
        menu_setting.whatsapp_enabled = "menu_whatsapp_enabled" in request.POST
        menu_setting.telegram_enabled = "menu_telegram_enabled" in request.POST
        update_fields.extend(("whatsapp_enabled", "telegram_enabled"))
    menu_setting.updated_by = request.user
    menu_setting.save(update_fields=update_fields)


@login_required
@super_admin_required
def whatsapp_status(request):
    payload, status_code = _gateway_request("GET", f"/sessions/{settings.WA_GATEWAY_SESSION}/status")
    _sync_whatsapp_status(payload)
    return JsonResponse(payload, status=status_code)


@login_required
@super_admin_required
def whatsapp_start(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method tidak diizinkan."}, status=405)
    payload, status_code = _gateway_request("POST", f"/sessions/{settings.WA_GATEWAY_SESSION}/start")
    _sync_whatsapp_status(payload)
    return JsonResponse(payload, status=status_code)


@login_required
@super_admin_required
def whatsapp_logout(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method tidak diizinkan."}, status=405)
    payload, status_code = _gateway_request("POST", f"/sessions/{settings.WA_GATEWAY_SESSION}/logout")
    _sync_whatsapp_status(payload)
    if bool(payload.get("ok")) and 200 <= status_code < 300:
        alert_payload, _ = send_whatsapp_logout_telegram_alert(request.user)
        log_whatsapp_session_telegram_alert(alert_payload, "WhatsApp Gateway Logout", request.user)
    return JsonResponse(payload, status=status_code)


@login_required
@super_admin_required
def whatsapp_test_message(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method tidak diizinkan."}, status=405)
    payload, status_code = _gateway_request("POST", f"/sessions/{settings.WA_GATEWAY_SESSION}/test-message")
    _sync_whatsapp_status(payload)
    _log_whatsapp_test_message(payload, status_code, request.user)
    return JsonResponse(payload, status=status_code)


@login_required
@super_admin_required
def telegram_test_message(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method tidak diizinkan."}, status=405)

    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    request_payload = _json_body(request)
    bot_token = request_payload.get("bot_token") or setting.telegram_bot_token
    chat_id = request_payload.get("chat_id") or setting.telegram_default_chat_id

    payload, status_code = _send_telegram_test_message(bot_token, chat_id, request.user)
    _log_telegram_test_message(payload, status_code, chat_id, request.user)
    return JsonResponse(payload, status=status_code)


@login_required
@super_admin_required
def telegram_fetch_chat_id(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method tidak diizinkan."}, status=405)

    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    request_payload = _json_body(request)
    bot_token = request_payload.get("bot_token") or setting.telegram_bot_token
    user_id = request_payload.get("user_id")

    payload, status_code = _fetch_latest_telegram_chat(bot_token)
    if not payload.get("ok"):
        return JsonResponse(payload, status=status_code)

    User = get_user_model()
    try:
        account = User.objects.get(pk=user_id, is_active=True)
    except (User.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Pilih pengguna yang akan dihubungkan ke Telegram."}, status=400)

    account.telegram_chat_id = str(payload["chat_id"])
    account.save(update_fields=["telegram_chat_id"])
    if not setting.telegram_default_chat_id:
        setting.telegram_default_chat_id = account.telegram_chat_id
        setting.updated_by = request.user
        setting.save(update_fields=["telegram_default_chat_id", "updated_by", "updated_at"])

    reply_payload = None
    if payload.get("message_text", "").strip().lower().startswith("/start"):
        reply_payload, _ = _send_telegram_start_reply(bot_token, account.telegram_chat_id, payload.get("chat_name", ""))
        _log_telegram_start_reply(reply_payload, account.telegram_chat_id, payload.get("chat_name", ""), request.user)

    return JsonResponse({
        "ok": True,
        "chat_id": account.telegram_chat_id,
        "chat_name": payload.get("chat_name", ""),
        "username": account.username,
        "display_name": account.display_name,
        "message": _telegram_fetch_success_message(account.display_name, reply_payload),
    })


def _save_setting_form(form, request):
    if not form.is_valid():
        messages.error(request, "Setting belum lengkap.")
        return False
    saved = form.save(commit=False)
    saved.updated_by = request.user
    saved.save()
    return True


def _notification_stats():
    logs = NotificationLog.objects
    return {
        "whatsapp_total": logs.filter(channel=NotificationLog.Channel.WHATSAPP).count(),
        "telegram_total": logs.filter(channel=NotificationLog.Channel.TELEGRAM).count(),
        "whatsapp_failed": logs.filter(
            channel=NotificationLog.Channel.WHATSAPP,
            status=NotificationLog.Status.FAILED,
        ).count(),
        "telegram_failed": logs.filter(
            channel=NotificationLog.Channel.TELEGRAM,
            status=NotificationLog.Status.FAILED,
        ).count(),
        "queued_total": logs.filter(status=NotificationLog.Status.QUEUED).count(),
    }


def _log_whatsapp_test_message(payload, status_code, user):
    is_sent = bool(payload.get("ok")) and 200 <= status_code < 300
    NotificationLog.objects.create(
        channel=NotificationLog.Channel.WHATSAPP,
        recipient=payload.get("target", ""),
        recipient_name="Akun WhatsApp session",
        subject="Tes Pesan WhatsApp",
        message=payload.get("message", "Tes pesan WhatsApp dari SIKAP-PU."),
        status=NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED,
        error_message=payload.get("error", ""),
        context_label="Notifikasi",
        sent_at=timezone.now() if is_sent else None,
        triggered_by=user if getattr(user, "is_authenticated", False) else None,
    )


def _log_telegram_test_message(payload, status_code, chat_id, user):
    is_sent = bool(payload.get("ok")) and 200 <= status_code < 300
    NotificationLog.objects.create(
        channel=NotificationLog.Channel.TELEGRAM,
        recipient=chat_id or "",
        recipient_name="Chat ID Telegram",
        subject="Tes Pesan Telegram",
        message=payload.get("message", "Tes pesan Telegram dari SIKAP-PU."),
        status=NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED,
        error_message=payload.get("error", ""),
        provider_message_id=str(payload.get("message_id") or ""),
        context_label="Notifikasi",
        sent_at=timezone.now() if is_sent else None,
        triggered_by=user if getattr(user, "is_authenticated", False) else None,
    )


def _log_telegram_start_reply(payload, chat_id, chat_name, user):
    is_sent = bool(payload and payload.get("ok"))
    NotificationLog.objects.create(
        channel=NotificationLog.Channel.TELEGRAM,
        recipient=chat_id or "",
        recipient_name=chat_name or "Chat Telegram",
        subject="Balasan /start Telegram",
        message=payload.get("message", "Balasan /start Telegram SIKAP-PU.") if payload else "",
        status=NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED,
        error_message="" if is_sent else (payload or {}).get("error", "Gagal membalas /start Telegram."),
        provider_message_id=str((payload or {}).get("message_id") or ""),
        context_label="Notifikasi",
        sent_at=timezone.now() if is_sent else None,
        triggered_by=user if getattr(user, "is_authenticated", False) else None,
    )


def _json_body(request):
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _send_telegram_test_message(bot_token, chat_id, user):
    bot_token = str(bot_token or "").strip()
    chat_id = str(chat_id or "").strip()
    if not bot_token or not chat_id:
        return {
            "ok": False,
            "error": "Bot token dan Chat ID Telegram wajib diisi terlebih dahulu.",
        }, 400

    text = "\n".join([
        "Tes pesan Telegram SIKAP-PU berhasil.",
        "",
        f"Pengirim: {getattr(user, 'display_name', '') or getattr(user, 'username', 'Sistem')}",
        f"Waktu: {timezone.localtime().strftime('%d-%m-%Y %H:%M')} WITA",
    ])
    return send_telegram_message(bot_token, chat_id, text, f"Pesan tes Telegram terkirim ke Chat ID {chat_id}.")


def _send_telegram_start_reply(bot_token, chat_id, chat_name):
    text = "\n".join([
        "Halo, SIKAP-PU sudah terhubung dengan Telegram Anda.",
        "",
        f"Chat ID Anda: {chat_id}",
        f"Nama chat: {chat_name or '-'}",
        "",
        "Simpan Chat ID ini di data pengguna agar notifikasi dapat dikirim otomatis.",
    ])
    return send_telegram_message(bot_token, chat_id, text, f"Balasan /start terkirim ke Chat ID {chat_id}.")


def _fetch_latest_telegram_chat(bot_token):
    bot_token = str(bot_token or "").strip()
    if not bot_token:
        return {"ok": False, "error": "Bot token Telegram wajib diisi terlebih dahulu."}, 400

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        with urlrequest.urlopen(url, timeout=12) as response:
            telegram_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        try:
            telegram_payload = json.loads(exc.read().decode("utf-8"))
            description = telegram_payload.get("description") or str(exc)
        except (json.JSONDecodeError, UnicodeDecodeError):
            description = str(exc)
        return {"ok": False, "error": f"Telegram gagal membaca update: {description}"}, exc.code
    except error.URLError as exc:
        return {"ok": False, "error": f"Telegram tidak dapat dihubungi: {exc.reason}"}, 503
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"ok": False, "error": "Telegram memberi respons yang tidak valid."}, 502

    if not telegram_payload.get("ok"):
        return {
            "ok": False,
            "error": telegram_payload.get("description") or "Telegram menolak permintaan getUpdates.",
        }, 502

    updates = telegram_payload.get("result") or []
    for update in reversed(updates):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id:
            full_name = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            return {
                "ok": True,
                "chat_id": str(chat_id),
                "chat_name": full_name or chat.get("username") or chat.get("title") or str(chat_id),
                "message_text": message.get("text", ""),
            }, 200

    return {
        "ok": False,
        "error": "Belum ada chat masuk. Buka Telegram, chat /start ke bot, lalu klik Ambil Chat ID lagi.",
    }, 404


def _telegram_fetch_success_message(display_name, reply_payload):
    if reply_payload and reply_payload.get("ok"):
        return f"Chat ID Telegram berhasil disimpan untuk {display_name}, dan bot sudah membalas /start."
    if reply_payload and reply_payload.get("error"):
        return f"Chat ID Telegram berhasil disimpan untuk {display_name}, tetapi balasan /start gagal: {reply_payload['error']}"
    return f"Chat ID Telegram berhasil disimpan untuk {display_name}."


def _gateway_request(method, path):
    url = f"{settings.WA_GATEWAY_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if settings.WA_GATEWAY_API_KEY:
        headers["x-api-key"] = settings.WA_GATEWAY_API_KEY
    data = b"{}" if method == "POST" else None
    gateway_request = urlrequest.Request(url, data=data, headers=headers, method=method)
    try:
        with urlrequest.urlopen(gateway_request, timeout=8) as response:
            return json.loads(response.read().decode("utf-8")), response.status
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"ok": False, "error": str(exc)}
        return payload, exc.code
    except error.URLError as exc:
        return {"ok": False, "status": "offline", "error": f"Wa-Gateway tidak terhubung: {exc.reason}"}, 503


def _sync_whatsapp_status(payload):
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    if payload.get("status") == "active":
        setting.whatsapp_connection_status = NotificationSetting.WhatsAppStatus.ACTIVE
        if not setting.whatsapp_last_login_at:
            setting.whatsapp_last_login_at = timezone.now()
    elif payload.get("status") in {"need_login", "offline", "connecting"}:
        setting.whatsapp_connection_status = NotificationSetting.WhatsAppStatus.NEED_LOGIN
    setting.save(update_fields=["whatsapp_connection_status", "whatsapp_last_login_at", "updated_at"])
