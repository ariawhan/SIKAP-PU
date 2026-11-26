import json
from datetime import timedelta
from urllib import error, parse, request as urlrequest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .models import CaseReminderDispatch, DocumentIssuedDispatch, NotificationLog, NotificationMenuSetting, NotificationSetting, NotificationTemplate, WebNotification
from .template_defaults import APP_NAME, DOCUMENT_ISSUED_STAGES, TEMPLATE_DEFINITIONS, issued_template_key


def ensure_notification_templates():
    legacy_deadline_templates = {
        channel: NotificationTemplate.objects.filter(
            key=f"case_deadline_{channel}",
        ).first()
        for channel in ("web", "whatsapp", "telegram")
    }
    templates = []
    for key, definition in TEMPLATE_DEFINITIONS.items():
        legacy = next((
            template
            for channel, template in legacy_deadline_templates.items()
            if template and key.endswith(f"_deadline_{channel}")
        ), None)
        template, _ = NotificationTemplate.objects.get_or_create(
            key=key,
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "channel": definition["channel"],
                "subject_template": (
                    legacy.subject_template if legacy else definition["subject"]
                ),
                "body_template": (
                    legacy.body_template if legacy else definition["body"]
                ),
            },
        )
        templates.append(template)
    NotificationTemplate.objects.filter(
        key__in=(
            "case_deadline_web",
            "case_deadline_whatsapp",
            "case_deadline_telegram",
        ),
    ).delete()
    return templates


def ensure_notification_menu_settings():
    settings_by_menu = []
    for menu_key, _ in NotificationMenuSetting.Menu.choices:
        menu_setting, _ = NotificationMenuSetting.objects.get_or_create(menu_key=menu_key)
        settings_by_menu.append(menu_setting)
    return settings_by_menu


def notification_menu_channels(menu_key):
    menu_setting = NotificationMenuSetting.objects.filter(menu_key=menu_key).first()
    if not menu_setting:
        return {"web": True, "whatsapp": True, "telegram": True}
    return {
        "web": menu_setting.web_enabled,
        "whatsapp": menu_setting.whatsapp_enabled,
        "telegram": menu_setting.telegram_enabled,
    }


def render_notification_template(key, context):
    definition = TEMPLATE_DEFINITIONS[key]
    template = NotificationTemplate.objects.filter(key=key).first()
    subject_template = template.subject_template if template else definition["subject"]
    body_template = template.body_template if template else definition["body"]
    values = {"nama_aplikasi": APP_NAME, **context}
    try:
        return {
            "subject": subject_template.format_map(values),
            "body": body_template.format_map(values),
        }
    except (KeyError, ValueError):
        # Template bawaan selalu menjadi pagar pengaman bila data lama/tidak valid tersimpan.
        return {
            "subject": definition["subject"].format_map(values),
            "body": definition["body"].format_map(values),
        }


def _numbered_names(users, empty_text):
    names = []
    seen = set()
    for user in users:
        if not user or not getattr(user, "is_active", True):
            continue
        identity = getattr(user, "pk", None) or user.display_name.casefold()
        if identity in seen:
            continue
        seen.add(identity)
        names.append(user.display_name)
    return "; ".join(
        f"{index}. {name}" for index, name in enumerate(names, start=1)
    ) or empty_text


def case_detail_template_context(spdp, assignment=None):
    """Data pelaku/terlapor dan seluruh tim yang dapat dipakai semua template perkara."""
    suspects = list(spdp.suspects.all())
    suspect_names = []
    for index, suspect in enumerate(suspects, start=1):
        label = suspect.get_suspect_type_display() or "Pelaku/Terlapor"
        alias = f" alias {suspect.alias}" if suspect.alias else ""
        suspect_names.append(f"{index}. {suspect.name}{alias} ({label})")
    daftar_pelaku = "; ".join(suspect_names) or "Masih terlapor (nama belum tersedia)"

    assignment = assignment or getattr(spdp, "p16_assignment", None)
    prosecutors = []
    administrative_staff = []
    if assignment:
        prosecutors.extend(assignment.prosecutors.all())
        prosecutors.extend(assignment.appointed_prosecutors.all())
        administrative_staff.extend(assignment.administrative_staff.all())
    return {
        "daftar_pelaku": daftar_pelaku,
        "daftar_jaksa": _numbered_names(prosecutors, "Belum ada Jaksa yang ditunjuk"),
        "daftar_pegawai": _numbered_names(
            administrative_staff, "Belum ada petugas administrasi yang ditunjuk",
        ),
    }


def send_telegram_message(bot_token, chat_id, text, success_message):
    bot_token = str(bot_token or "").strip()
    chat_id = str(chat_id or "").strip()
    if not bot_token or not chat_id:
        return {
            "ok": False,
            "error": "Bot token dan Chat ID Telegram wajib diisi terlebih dahulu.",
        }, 400

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    telegram_request = urlrequest.Request(
        url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(telegram_request, timeout=12) as response:
            telegram_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        try:
            telegram_payload = json.loads(exc.read().decode("utf-8"))
            description = telegram_payload.get("description") or str(exc)
        except (json.JSONDecodeError, UnicodeDecodeError):
            description = str(exc)
        return {"ok": False, "error": f"Telegram gagal mengirim pesan: {description}"}, exc.code
    except error.URLError as exc:
        return {"ok": False, "error": f"Telegram tidak dapat dihubungi: {exc.reason}"}, 503
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"ok": False, "error": "Telegram memberi respons yang tidak valid."}, 502

    if not telegram_payload.get("ok"):
        return {
            "ok": False,
            "error": telegram_payload.get("description") or "Telegram menolak pengiriman pesan.",
        }, 502

    result = telegram_payload.get("result") or {}
    return {
        "ok": True,
        "message": success_message,
        "message_id": result.get("message_id"),
    }, 200


def send_whatsapp_logout_telegram_alert(user=None, reason="logout"):
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    actor = getattr(user, "display_name", "") or getattr(user, "username", "Sistem")
    reason_text = "terdeteksi logout otomatis" if reason == "monitor" else "telah logout"
    rendered = render_notification_template("whatsapp_logout_telegram", {
        "status_session": reason_text,
        "oleh": actor,
        "waktu": timezone.localtime().strftime("%d-%m-%Y %H:%M"),
    })
    return send_telegram_message(
        setting.telegram_bot_token,
        setting.telegram_default_chat_id,
        rendered["body"],
        "Alert logout WhatsApp terkirim ke Telegram admin.",
    )


def send_whatsapp_recovered_telegram_alert():
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    rendered = render_notification_template("whatsapp_recovered_telegram", {
        "waktu": timezone.localtime().strftime("%d-%m-%Y %H:%M"),
    })
    return send_telegram_message(
        setting.telegram_bot_token,
        setting.telegram_default_chat_id,
        rendered["body"],
        "Info WhatsApp aktif kembali terkirim ke Telegram admin.",
    )


def log_whatsapp_session_telegram_alert(payload, subject, user=None):
    is_sent = bool(payload and payload.get("ok"))
    setting = NotificationSetting.objects.filter(pk=1).first()
    NotificationLog.objects.create(
        channel=NotificationLog.Channel.TELEGRAM,
        recipient=(setting.telegram_default_chat_id if setting else "") or "",
        recipient_name="Admin Telegram",
        subject=subject,
        message=payload.get("message", subject) if payload else "",
        status=NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED,
        error_message="" if is_sent else (payload or {}).get("error", "Gagal mengirim alert WhatsApp ke Telegram."),
        provider_message_id=str((payload or {}).get("message_id") or ""),
        context_label="WhatsApp Monitor",
        sent_at=timezone.now() if is_sent else None,
        triggered_by=user if getattr(user, "is_authenticated", False) else None,
    )


def send_whatsapp_message(phone_number, text):
    phone_number = normalize_whatsapp_number(phone_number)
    if not phone_number or not str(text or "").strip():
        return {
            "ok": False,
            "error": "Nomor WhatsApp penerima dan isi pesan wajib tersedia.",
        }, 400

    url = f"{settings.WA_GATEWAY_URL}/messages/send-text"
    body = json.dumps({
        "sessionId": settings.WA_GATEWAY_SESSION,
        "to": phone_number,
        "text": text,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.WA_GATEWAY_API_KEY:
        headers["x-api-key"] = settings.WA_GATEWAY_API_KEY
    gateway_request = urlrequest.Request(url, data=body, headers=headers, method="POST")
    try:
        with urlrequest.urlopen(gateway_request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload, response.status
    except error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"ok": False, "error": str(exc)}
        return payload, exc.code
    except error.URLError as exc:
        return {
            "ok": False,
            "error": f"Wa-Gateway tidak dapat dihubungi: {exc.reason}",
        }, 503
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"ok": False, "error": "Wa-Gateway memberi respons yang tidak valid."}, 502


def normalize_whatsapp_number(phone_number):
    number = "".join(character for character in str(phone_number or "") if character.isdigit())
    if number.startswith("0"):
        number = f"62{number[1:]}"
    return number


@transaction.atomic
def enqueue_external_notification(
    *, channel, recipient, recipient_name, subject, message,
    context_label="", actor=None,
):
    """Tambahkan pesan ke antrean dengan jarak minimum dua menit per kanal."""
    recipient = str(recipient or "").strip()
    actor = actor if getattr(actor, "is_authenticated", False) else None
    now = timezone.now()
    if not recipient:
        return NotificationLog.objects.create(
            channel=channel,
            recipient="",
            recipient_name=recipient_name,
            subject=subject,
            message=message,
            status=NotificationLog.Status.FAILED,
            error_message=(
                "Nomor WhatsApp penerima belum diisi."
                if channel == NotificationLog.Channel.WHATSAPP
                else "Chat ID Telegram penerima belum diisi."
            ),
            context_label=context_label,
            attempted_at=now,
            triggered_by=actor,
        )

    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    NotificationSetting.objects.select_for_update().get(pk=setting.pk)
    message_gap = timedelta(minutes=setting.outbound_message_delay_minutes)
    scheduled_at = now
    latest_queued = (
        NotificationLog.objects.filter(
            channel=channel,
            status__in=(
                NotificationLog.Status.QUEUED,
                NotificationLog.Status.PROCESSING,
            ),
            scheduled_at__isnull=False,
        )
        .order_by("-scheduled_at", "-pk")
        .first()
    )
    if latest_queued:
        scheduled_at = max(
            scheduled_at,
            latest_queued.scheduled_at + message_gap,
        )
    latest_attempt = (
        NotificationLog.objects.filter(
            channel=channel,
            attempted_at__isnull=False,
        )
        .order_by("-attempted_at", "-pk")
        .first()
    )
    if latest_attempt:
        scheduled_at = max(
            scheduled_at,
            latest_attempt.attempted_at + message_gap,
        )
    return NotificationLog.objects.create(
        channel=channel,
        recipient=recipient,
        recipient_name=recipient_name,
        subject=subject,
        message=message,
        status=NotificationLog.Status.QUEUED,
        context_label=context_label,
        scheduled_at=scheduled_at,
        triggered_by=actor,
    )


def process_notification_queue(now=None):
    """Kirim maksimal satu pesan jatuh tempo per kanal pada setiap pemeriksaan."""
    now = now or timezone.now()
    processed = 0
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    message_gap = timedelta(minutes=setting.outbound_message_delay_minutes)
    for channel in (NotificationLog.Channel.WHATSAPP, NotificationLog.Channel.TELEGRAM):
        with transaction.atomic():
            queued = (
                NotificationLog.objects.select_for_update()
                .filter(
                    channel=channel,
                    status=NotificationLog.Status.QUEUED,
                    scheduled_at__lte=now,
                )
                .order_by("scheduled_at", "pk")
                .first()
            )
            if not queued:
                continue
            latest_attempt = (
                NotificationLog.objects.filter(
                    channel=channel,
                    attempted_at__isnull=False,
                )
                .exclude(pk=queued.pk)
                .order_by("-attempted_at", "-pk")
                .first()
            )
            if latest_attempt and latest_attempt.attempted_at + message_gap > now:
                queued.scheduled_at = latest_attempt.attempted_at + message_gap
                queued.save(update_fields=("scheduled_at",))
                continue
            queued.status = NotificationLog.Status.PROCESSING
            queued.attempted_at = now
            queued.save(update_fields=("status", "attempted_at"))

        try:
            if channel == NotificationLog.Channel.WHATSAPP:
                payload, status_code = send_whatsapp_message(
                    queued.recipient, queued.message,
                )
            else:
                payload, status_code = send_telegram_message(
                    setting.telegram_bot_token,
                    queued.recipient,
                    queued.message,
                    f"Pesan Telegram terkirim kepada {queued.recipient_name}.",
                )
        except Exception as exc:
            payload, status_code = {
                "ok": False,
                "error": f"Pengiriman {queued.get_channel_display()} gagal: {exc}",
            }, 500

        is_sent = bool(payload and payload.get("ok") and 200 <= status_code < 300)
        queued.status = (
            NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED
        )
        queued.provider_message_id = _provider_message_id(payload)
        queued.error_message = "" if is_sent else (
            (payload or {}).get("error") or "Pengiriman notifikasi gagal."
        )
        queued.sent_at = timezone.now() if is_sent else None
        queued.save(update_fields=(
            "status", "provider_message_id", "error_message", "sent_at",
        ))
        processed += 1
    return processed


def create_p16_assignment_web_notification(assignment, actor=None):
    if not notification_menu_channels(NotificationMenuSetting.Menu.P16)["web"]:
        return None
    messages = build_p16_assignment_messages(assignment)
    return WebNotification.objects.create(
        recipient=assignment.kasi_pidum,
        kind=WebNotification.Kind.P16_ASSIGNMENT,
        title=messages["subject"],
        message=messages["web"],
        target_url=reverse("cases:spdp_list"),
        context_label=f"SPDP {assignment.spdp.letter_number}",
        spdp=assignment.spdp,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


def send_p16_assignment_external_notifications(assignment_id, actor_id=None):
    # Import lokal mencegah ketergantungan melingkar antara app perkara dan notifikasi.
    from cases.models import P16Assignment

    assignment = P16Assignment.objects.select_related("spdp", "kasi_pidum", "started_by").get(pk=assignment_id)
    actor = get_user_model().objects.filter(pk=actor_id).first() if actor_id else None
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    notification_messages = build_p16_assignment_messages(assignment)
    context_label = f"P-16 | {assignment.spdp.letter_number}"
    menu_channels = notification_menu_channels(NotificationMenuSetting.Menu.P16)

    if setting.whatsapp_enabled and menu_channels["whatsapp"]:
        recipient = normalize_whatsapp_number(assignment.kasi_pidum.whatsapp_number)
        enqueue_external_notification(
            channel=NotificationLog.Channel.WHATSAPP,
            recipient=recipient,
            recipient_name=assignment.kasi_pidum.display_name,
            subject=notification_messages["whatsapp_subject"],
            message=notification_messages["whatsapp"],
            context_label=context_label,
            actor=actor,
        )

    if setting.telegram_enabled and menu_channels["telegram"]:
        recipient = str(assignment.kasi_pidum.telegram_chat_id or "").strip()
        enqueue_external_notification(
            channel=NotificationLog.Channel.TELEGRAM,
            recipient=recipient,
            recipient_name=assignment.kasi_pidum.display_name,
            subject=notification_messages["telegram_subject"],
            message=notification_messages["telegram"],
            context_label=context_label,
            actor=actor,
        )


@transaction.atomic
def send_document_issued_notifications(
    *, spdp_id, stage_key, document_id, document_number, document_date,
    actor_id=None,
):
    """Kirim notifikasi terbit sekali kepada seluruh tim penanganan perkara."""
    from accounts.models import Role
    from cases.models import P16Assignment, SPDP

    if stage_key not in DOCUMENT_ISSUED_STAGES:
        raise ValueError(f"Tahapan notifikasi terbit tidak dikenal: {stage_key}")

    spdp = SPDP.objects.prefetch_related("suspects", "investigators").get(pk=spdp_id)
    dispatch, created = DocumentIssuedDispatch.objects.get_or_create(
        stage_key=stage_key,
        document_id=document_id,
        defaults={
            "spdp": spdp,
            "document_number": str(document_number or "").strip(),
        },
    )
    if not created:
        return 0

    assignment = (
        P16Assignment.objects.filter(spdp_id=spdp_id)
        .select_related("kasi_pidum")
        .prefetch_related("prosecutors", "appointed_prosecutors", "administrative_staff")
        .first()
    )
    recipients = {}
    if assignment:
        candidates = [assignment.kasi_pidum]
        candidates.extend(assignment.prosecutors.filter(is_active=True))
        candidates.extend(assignment.administrative_staff.filter(is_active=True))
        for recipient in candidates:
            if recipient and recipient.is_active:
                recipients[recipient.pk] = recipient
    for recipient in get_user_model().objects.filter(
        is_active=True, roles__code=Role.KASUBSI_PREPROSECUTION,
    ).distinct():
        recipients[recipient.pk] = recipient

    actor = get_user_model().objects.filter(pk=actor_id).first() if actor_id else None
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    menu_channels = notification_menu_channels(stage_key)
    stage_label = DOCUMENT_ISSUED_STAGES[stage_key]
    formatted_date = (
        date_format(document_date, "d F Y", use_l10n=True)
        if document_date else "-"
    )
    context_label = f"{stage_label} Terbit | {spdp.letter_number}"
    target_url = _issued_document_target_url(stage_key, document_id, spdp_id)
    case_details = case_detail_template_context(spdp, assignment)

    for recipient in recipients.values():
        context = {
            "nama_penerima": recipient.display_name,
            "tahapan": stage_label,
            "nomor_surat": str(document_number or "-").strip() or "-",
            "nomor_spdp": spdp.letter_number,
            "tanggal_surat": formatted_date,
            **case_details,
        }
        if menu_channels["web"]:
            rendered = render_notification_template(
                issued_template_key(stage_key, "web"), context,
            )
            WebNotification.objects.create(
                recipient=recipient,
                kind=WebNotification.Kind.DOCUMENT_ISSUED,
                title=rendered["subject"],
                message=rendered["body"],
                target_url=target_url,
                context_label=context_label,
                spdp=spdp,
                created_by=actor,
            )
        if setting.whatsapp_enabled and menu_channels["whatsapp"]:
            rendered = render_notification_template(
                issued_template_key(stage_key, "whatsapp"), context,
            )
            enqueue_external_notification(
                channel=NotificationLog.Channel.WHATSAPP,
                recipient=normalize_whatsapp_number(recipient.whatsapp_number),
                recipient_name=recipient.display_name,
                subject=rendered["subject"],
                message=rendered["body"],
                context_label=context_label,
                actor=actor,
            )
        if setting.telegram_enabled and menu_channels["telegram"]:
            rendered = render_notification_template(
                issued_template_key(stage_key, "telegram"), context,
            )
            enqueue_external_notification(
                channel=NotificationLog.Channel.TELEGRAM,
                recipient=str(recipient.telegram_chat_id or "").strip(),
                recipient_name=recipient.display_name,
                subject=rendered["subject"],
                message=rendered["body"],
                context_label=context_label,
                actor=actor,
            )

    investigator_recipient_count = 0
    investigator_notification_stages = {
        "p16", "p17", "sop02", "sop03", "p18", "p19", "p21",
    }
    if stage_key in investigator_notification_stages:
        investigator_context_label = (
            f"{stage_label} Terbit untuk Penyidik | {spdp.letter_number}"
        )
        for investigator in spdp.investigators.all():
            context = {
                "nama_penyidik": investigator.name,
                "nomor_surat": str(document_number or "-").strip() or "-",
                "nomor_spdp": spdp.letter_number,
                "tanggal_surat": formatted_date,
                "daftar_pelaku": case_details["daftar_pelaku"],
                "daftar_jaksa": case_details["daftar_jaksa"],
            }
            queued_for_investigator = False
            if setting.whatsapp_enabled and menu_channels["whatsapp"]:
                rendered = render_notification_template(
                    f"{stage_key}_investigator_issued_whatsapp", context,
                )
                enqueue_external_notification(
                    channel=NotificationLog.Channel.WHATSAPP,
                    recipient=normalize_whatsapp_number(investigator.phone),
                    recipient_name=investigator.name,
                    subject=rendered["subject"],
                    message=rendered["body"],
                    context_label=investigator_context_label,
                    actor=actor,
                )
                queued_for_investigator = True
            investigator_telegram_id = str(investigator.telegram_chat_id or "").strip()
            if (
                investigator_telegram_id
                and setting.telegram_enabled
                and menu_channels["telegram"]
            ):
                rendered = render_notification_template(
                    f"{stage_key}_investigator_issued_telegram", context,
                )
                enqueue_external_notification(
                    channel=NotificationLog.Channel.TELEGRAM,
                    recipient=investigator_telegram_id,
                    recipient_name=investigator.name,
                    subject=rendered["subject"],
                    message=rendered["body"],
                    context_label=investigator_context_label,
                    actor=actor,
                )
                queued_for_investigator = True
            if queued_for_investigator:
                investigator_recipient_count += 1

    total_recipient_count = len(recipients) + investigator_recipient_count
    dispatch.recipient_count = total_recipient_count
    dispatch.save(update_fields=("recipient_count",))
    return total_recipient_count


def _issued_document_target_url(stage_key, document_id, spdp_id):
    url_names = {
        "p16": "cases:p16_draft_detail",
        "p17": "cases:p17_draft_detail",
        "sop02": "cases:sop_form_02_detail",
        "sop03": "cases:sop_form_03_detail",
        "p18": "cases:p18_detail",
        "p19": "cases:p19_detail",
        "p20": "cases:p20_detail",
        "p21": "cases:p21_draft_detail",
        "sop07": "cases:sop_form_07_detail",
    }
    if stage_key == "stage1":
        return reverse("cases:stage_one_detail", args=(spdp_id,))
    return reverse(url_names[stage_key], args=(document_id,))


def send_sop_form_03_issued_notifications(draft_id, actor_id=None):
    from cases.models import SOPForm03Draft

    draft = SOPForm03Draft.objects.select_related("spdp").get(pk=draft_id)
    return send_document_issued_notifications(
        spdp_id=draft.spdp_id,
        stage_key=NotificationMenuSetting.Menu.SOP_FORM_03,
        document_id=draft.pk,
        document_number=draft.letter_number,
        document_date=draft.letter_date,
        actor_id=actor_id,
    )


def build_p16_assignment_messages(assignment):
    from cases.reminders import SPDP_PERIOD_DAYS

    spdp = assignment.spdp
    kasi = assignment.kasi_pidum
    due_date = spdp.received_date + timedelta(days=SPDP_PERIOD_DAYS)
    remaining_days = (due_date - timezone.localdate()).days
    deadline_status = _deadline_status_text(remaining_days)
    received_date = date_format(spdp.received_date, "d F Y", use_l10n=True)
    formatted_due_date = date_format(due_date, "d F Y", use_l10n=True)
    suspect_count = spdp.suspects.count()
    suspect_label = f"{suspect_count} orang" if suspect_count else "Belum ada data pelaku"
    actor = assignment.started_by.display_name if assignment.started_by_id else f"Petugas {APP_NAME}"
    context = {
        "nama_penerima": kasi.display_name,
        "nomor_spdp": spdp.letter_number,
        "tanggal_diterima": received_date,
        "jumlah_pelaku": suspect_label,
        "batas_p16": formatted_due_date,
        "status_waktu": deadline_status,
        "diteruskan_oleh": actor,
        **case_detail_template_context(spdp, assignment),
    }
    web = render_notification_template("p16_assignment_web", context)
    whatsapp = render_notification_template("p16_assignment_whatsapp", context)
    telegram = render_notification_template("p16_assignment_telegram", context)
    return {
        "subject": web["subject"],
        "web": web["body"],
        "whatsapp_subject": whatsapp["subject"],
        "whatsapp": whatsapp["body"],
        "telegram_subject": telegram["subject"],
        "telegram": telegram["body"],
        "external": whatsapp["body"],
    }


def _deadline_status_text(remaining_days):
    if remaining_days > 1:
        return f"tersisa {remaining_days} hari"
    if remaining_days == 1:
        return "tersisa 1 hari"
    if remaining_days == 0:
        return "batas waktu hari ini"
    return f"terlambat {abs(remaining_days)} hari"


def _log_assignment_delivery(*, channel, recipient, assignment, actor, subject, message, payload, status_code, context_label):
    is_sent = bool(payload and payload.get("ok") and 200 <= status_code < 300)
    NotificationLog.objects.create(
        channel=channel,
        recipient=recipient,
        recipient_name=assignment.kasi_pidum.display_name,
        subject=subject,
        message=message,
        status=NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED,
        provider_message_id=_provider_message_id(payload),
        error_message="" if is_sent else (payload or {}).get("error", "Pengiriman notifikasi gagal."),
        context_label=context_label,
        sent_at=timezone.now() if is_sent else None,
        triggered_by=actor,
    )


def _provider_message_id(payload):
    if not payload:
        return ""
    direct_id = payload.get("message_id")
    if direct_id:
        return str(direct_id)
    result = payload.get("result") or {}
    if isinstance(result, dict):
        key = result.get("key") or {}
        return str(key.get("id") or result.get("id") or "")
    return ""


def case_deadline_recipients(spdp, stage_key=None):
    from accounts.models import Role

    users = {}
    assignment = getattr(spdp, "p16_assignment", None)
    if assignment:
        candidates = [assignment.kasi_pidum]
        candidates.extend(assignment.prosecutors.filter(is_active=True))
        candidates.extend(assignment.administrative_staff.filter(is_active=True))
        for user in candidates:
            if user and user.is_active:
                users[user.pk] = user
    for user in get_user_model().objects.filter(
        is_active=True, roles__code=Role.KASUBSI_PREPROSECUTION,
    ).distinct():
        users[user.pk] = user
    if stage_key == "spdp":
        for user in get_user_model().objects.filter(
            is_active=True,
            roles__code=Role.KASI_PIDUM,
        ).distinct():
            users[user.pk] = user
    return list(users.values())


def _case_deadline_context(deadline, recipient):
    return {
        "nama_penerima": recipient.display_name,
        "tahapan": deadline.stage_label,
        "hari_ke": deadline.elapsed_days,
        "nomor_spdp": deadline.spdp.letter_number,
        "nomor_surat": deadline.letter_number,
        "tanggal_surat": date_format(deadline.start_date, "d F Y", use_l10n=True),
        "tanggal_batas": date_format(deadline.due_date, "d F Y", use_l10n=True),
        "masa_hari": deadline.period_days,
        "status_waktu": deadline.status_text,
        "tindak_lanjut": deadline.action_text,
        **case_detail_template_context(deadline.spdp),
    }


def _log_case_deadline_delivery(*, channel, recipient, subject, message, payload, status_code, deadline, actor):
    is_sent = bool(payload and payload.get("ok") and 200 <= status_code < 300)
    NotificationLog.objects.create(
        channel=channel,
        recipient=recipient.telegram_chat_id if channel == NotificationLog.Channel.TELEGRAM else normalize_whatsapp_number(recipient.whatsapp_number),
        recipient_name=recipient.display_name,
        subject=subject,
        message=message,
        status=NotificationLog.Status.SENT if is_sent else NotificationLog.Status.FAILED,
        provider_message_id=_provider_message_id(payload),
        error_message="" if is_sent else (payload or {}).get("error", "Pengiriman notifikasi gagal."),
        context_label=f"{deadline.stage_label} | {deadline.spdp.letter_number}",
        sent_at=timezone.now() if is_sent else None,
        triggered_by=actor,
    )


def send_case_deadline_reminder(deadline, actor=None):
    recipients = case_deadline_recipients(deadline.spdp, deadline.stage_key)
    setting, _ = NotificationSetting.objects.get_or_create(pk=1)
    menu_channels = notification_menu_channels(deadline.stage_key)
    actor = actor if getattr(actor, "is_authenticated", False) else None
    for recipient in recipients:
        context = _case_deadline_context(deadline, recipient)
        if menu_channels["web"]:
            web = render_notification_template(
                f"{deadline.stage_key}_deadline_web", context,
            )
            WebNotification.objects.create(
                recipient=recipient,
                kind=WebNotification.Kind.CASE_DEADLINE,
                title=web["subject"],
                message=web["body"],
                target_url=deadline.target_url,
                context_label=f"{deadline.stage_label} | {deadline.spdp.letter_number}",
                spdp=deadline.spdp,
                created_by=actor,
            )
        if setting.whatsapp_enabled and menu_channels["whatsapp"]:
            rendered = render_notification_template(
                f"{deadline.stage_key}_deadline_whatsapp", context,
            )
            number = normalize_whatsapp_number(recipient.whatsapp_number)
            enqueue_external_notification(
                channel=NotificationLog.Channel.WHATSAPP,
                recipient=number,
                recipient_name=recipient.display_name,
                subject=rendered["subject"],
                message=rendered["body"],
                context_label=f"{deadline.stage_label} | {deadline.spdp.letter_number}",
                actor=actor,
            )
        if setting.telegram_enabled and menu_channels["telegram"]:
            rendered = render_notification_template(
                f"{deadline.stage_key}_deadline_telegram", context,
            )
            chat_id = str(recipient.telegram_chat_id or "").strip()
            enqueue_external_notification(
                channel=NotificationLog.Channel.TELEGRAM,
                recipient=chat_id,
                recipient_name=recipient.display_name,
                subject=rendered["subject"],
                message=rendered["body"],
                context_label=f"{deadline.stage_label} | {deadline.spdp.letter_number}",
                actor=actor,
            )
    return len(recipients)


def process_due_case_deadline_reminders(today=None):
    from cases.reminders import active_case_deadlines

    today = today or timezone.localdate()
    sent = 0
    for deadline in active_case_deadlines(today):
        if not deadline.automatic_due:
            continue
        dispatch, created = CaseReminderDispatch.objects.get_or_create(
            spdp=deadline.spdp,
            stage_key=deadline.stage_key,
            document_id=deadline.document_id,
            reminder_day=deadline.elapsed_days,
        )
        if not created:
            continue
        dispatch.recipient_count = send_case_deadline_reminder(deadline)
        dispatch.save(update_fields=("recipient_count",))
        sent += 1
    return sent


def close_case_deadline_notifications(spdp):
    removed = WebNotification.objects.filter(
        spdp=spdp,
        kind__in=(
            WebNotification.Kind.CASE_DEADLINE,
            WebNotification.Kind.P16_ASSIGNMENT,
        ),
    ).delete()[0]
    removed += WebNotification.objects.filter(
        spdp__isnull=True,
        kind=WebNotification.Kind.P16_ASSIGNMENT,
        context_label=f"SPDP {spdp.letter_number}",
    ).delete()[0]
    return removed


def close_p21_deadline_notifications(spdp):
    context_label = f"P-21 | {spdp.letter_number}"
    removed = WebNotification.objects.filter(
        spdp=spdp,
        kind=WebNotification.Kind.CASE_DEADLINE,
        context_label=context_label,
    ).delete()[0]
    removed += NotificationLog.objects.filter(
        context_label=context_label,
        status=NotificationLog.Status.QUEUED,
    ).update(
        status=NotificationLog.Status.CANCELLED,
        error_message="P-21 sudah dilaksanakan; reminder dibatalkan.",
    )
    return removed
