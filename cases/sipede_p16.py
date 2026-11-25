"""Pengambilan nomor dan upload P-16 ke Administrasi Perkara SIPede."""

import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from configurations import sipede
from configurations.models import InstitutionConfiguration, SipedeIntegration
from .p16_numbering import p16_number_parts


P16_CREATE_URL = f"{sipede.SIPEDE_BASE_URL}/administrasiperkara/create?idSurat=5"
P16_DISPOSITION_OPTIONS_URL = f"{sipede.SIPEDE_BASE_URL}/suratkeluar/get-master-tujuan-disposisi"
P16_ID_SURAT = "5"
P16_JENIS_SURAT = "14"
P16_SIFAT = "PRIN"
P16_TUJUAN = "KEPALA KEJAKSAAN NEGERI BULELENG"
P16_PERIHAL = (
    "PENUNJUKAN PENUNTUT UMUM UNTUK MENGIKUTI PERKEMBANGAN "
    "PENYIDIKAN PERKARA TINDAK PIDANA"
)
P16_ALLOWED_SIFAT = {"SR", "R", "T", "B", "KEP", "PRIN"}
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_PDF_BYTES = 18 * 1024 * 1024


class P16SipedeError(RuntimeError):
    pass


class P16SipedeLoginRequired(P16SipedeError):
    pass


def _normalized(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


_SIGNATORY_DEGREE_SUFFIXES = (
    ("SHI",), ("MHI",), ("SH",), ("MH",), ("SAG",), ("MAG",),
    ("SSOS",), ("MSI",), ("SKOM",), ("MKOM",), ("MSC",), ("LLM",),
    ("S", "H", "I"), ("M", "H", "I"), ("S", "H"), ("M", "H"),
    ("S", "A", "G"), ("M", "A", "G"), ("S", "S", "O", "S"),
    ("M", "S", "I"), ("S", "K", "O", "M"), ("M", "K", "O", "M"),
    ("D", "R"),
)


def _signatory_name_tokens(value):
    tokens = re.findall(r"[A-Z0-9]+", str(value or "").upper())
    changed = True
    while changed:
        changed = False
        for suffix in _SIGNATORY_DEGREE_SUFFIXES:
            if len(tokens) >= len(suffix) and tuple(tokens[-len(suffix):]) == suffix:
                del tokens[-len(suffix):]
                changed = True
                break
    return tokens


def match_option(options, target, label="Pilihan"):
    target = (target or "").strip()
    if not target:
        raise P16SipedeError(f"{label} belum dikonfigurasi.")
    for option in options:
        if str(option.get("value", "")).strip().casefold() == target.casefold():
            return str(option["value"]).strip()
    normalized_target = _normalized(target)
    for option in options:
        value = str(option.get("value", "")).strip()
        normalized_value = _normalized(value)
        normalized_label = _normalized(str(option.get("label", "")))
        if normalized_target == normalized_value or normalized_target in normalized_label:
            return value
    raise P16SipedeError(f"{label} '{target}' tidak ditemukan pada formulir SIPede.")


def match_signatory_option(options, target):
    try:
        return match_option(options, target, "Penanda tangan")
    except P16SipedeError as original_error:
        target_name = "".join(_signatory_name_tokens(target))
        if not target_name:
            raise original_error
        matching_values = set()
        for option in options:
            value = str(option.get("value", "")).strip()
            if value and target_name in _normalized(option.get("label", "")):
                matching_values.add(value)
        if len(matching_values) == 1:
            return matching_values.pop()
        if len(matching_values) > 1:
            raise P16SipedeError(
                f"Penanda tangan '{target}' cocok dengan lebih dari satu opsi SIPede."
            )
        raise original_error


def _integration_and_session(user):
    integration = SipedeIntegration.objects.filter(user=user).first()
    if not integration:
        raise P16SipedeLoginRequired(
            "Konfigurasi SIPede belum tersedia. Isi kredensial pada menu Integrasi SIPede."
        )
    if not integration.session_encrypted or not integration.connected_at:
        raise P16SipedeLoginRequired("Sesi SIPede belum aktif. Hubungkan akun SIPede terlebih dahulu.")
    try:
        session_data = json.loads(sipede.decrypt(integration.session_encrypted))
    except Exception as exc:
        raise P16SipedeLoginRequired("Sesi SIPede tidak dapat dibaca. Hubungkan ulang akun SIPede.") from exc
    if not session_data.get("cookies"):
        raise P16SipedeLoginRequired("Cookie sesi SIPede tidak tersedia. Hubungkan ulang akun SIPede.")
    return integration, session_data


def session_available(user):
    """Verify that the stored session is still accepted by SIPede."""
    integration, session_data = _integration_and_session(user)
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser, context, _page, form_context = _open_p16_form(playwright, session_data)
            _persist_session(integration, session_data, context, form_context)
            return True
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


def disposition_options(user):
    """Return the user's SIPede forwarding targets without choosing one automatically."""
    integration, session_data = _integration_and_session(user)
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser, context, _page, form_context = _open_p16_form(playwright, session_data)
            response = context.request.get(
                P16_DISPOSITION_OPTIONS_URL,
                headers={"Accept": "application/json", "Referer": P16_CREATE_URL},
                timeout=120000,
            )
            if not response.ok:
                raise P16SipedeError(
                    f"Daftar tujuan disposisi SIPede gagal dimuat (HTTP {response.status})."
                )
            try:
                payload = response.json()
            except Exception as exc:
                raise P16SipedeError("Respons daftar tujuan disposisi SIPede tidak valid.") from exc
            rows = payload.get("data", []) if isinstance(payload, dict) else []
            options = []
            for row in rows:
                value = str(row.get("id_tujuan_penerusan", "")).strip()
                if not value.isdigit():
                    continue
                users = row.get("user") if isinstance(row.get("user"), list) else []
                user_name = str(users[0].get("nama", "")).strip() if users and isinstance(users[0], dict) else ""
                position = str(row.get("nama_jabatan", "")).strip()
                label = f"{position} ({user_name or 'NO USER'})".strip()
                options.append({"value": value, "label": label})
            _persist_session(integration, session_data, context, form_context)
            return options
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


def _restore_cookies(context, session_data):
    allowed = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
    cookies = []
    for source in session_data.get("cookies", []):
        cookie = {key: value for key, value in source.items() if key in allowed and value is not None}
        if cookie.get("name") and cookie.get("value"):
            cookie.setdefault("domain", "sipede.kejaksaan.go.id")
            cookie.setdefault("path", "/")
            cookies.append(cookie)
    context.add_cookies(cookies)


def _read_form_context(page):
    return page.evaluate("""() => {
        const form = document.querySelector('#formCreateEdit');
        const optionsOf = (name) => Array.from(form?.querySelectorAll(`[name="${name}"] option`) || [])
          .map(option => ({value: option.value, label: option.textContent.trim()}))
          .filter(option => option.value);
        const valueOf = (selector) => document.querySelector(selector)?.value || '';
        return {
          csrf_token: valueOf('#formCreateEdit [name="_token"]') ||
            document.querySelector('meta[name="csrf-token"]')?.content || '',
          form_action: form?.action || '',
          id_surat: valueOf('#formCreateEdit [name="idSurat"]') || '5',
          jenis_surat: valueOf('[name="jenis_surat"]') || valueOf('[name="jenis"]') || '',
          jenis: valueOf('[name="jenis"]'),
          bidang_main: valueOf('[name="bidang_main"]'),
          jenis_options: optionsOf('jenis_surat').length ? optionsOf('jenis_surat') : optionsOf('jenis'),
          sifat_options: optionsOf('sifat'),
          kode_masalah_options: optionsOf('kode_masalah'),
          penandatangan_options: optionsOf('penandatangan'),
          field_names: Array.from(form?.elements || []).map(field => field.name).filter(Boolean)
        };
    }""")


def _trusted_sipede_url(url):
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and parsed.hostname == "sipede.kejaksaan.go.id"


def _open_p16_form(playwright, session_data):
    browser, context, page = sipede._open_browser(playwright, use_proxy=True)
    _restore_cookies(context, session_data)
    page.goto(P16_CREATE_URL, wait_until="domcontentloaded", timeout=60000)
    if "/login" in urlparse(page.url).path.lower():
        browser.close()
        raise P16SipedeLoginRequired("Sesi SIPede telah kedaluwarsa. Hubungkan ulang akun SIPede.")
    try:
        page.locator("#formCreateEdit").wait_for(state="attached", timeout=30000)
    except Exception as exc:
        login_required = "/login" in urlparse(page.url).path.lower() or page.locator(
            'input[type="password"], input[name="password"]'
        ).count()
        browser.close()
        if login_required:
            raise P16SipedeLoginRequired(
                "Sesi SIPede telah kedaluwarsa. Silakan login ulang."
            ) from exc
        raise P16SipedeError("Formulir Administrasi Perkara P-16 tidak ditemukan di SIPede.") from exc
    form_context = _read_form_context(page)
    if not form_context.get("csrf_token") or not _trusted_sipede_url(form_context.get("form_action")):
        browser.close()
        raise P16SipedeError("Token atau alamat formulir P-16 SIPede tidak valid.")
    return browser, context, page, form_context


def _metadata_targets(draft, signatory_name=None):
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    signer_name = (signatory_name or "").strip() or (
        draft.acting_name if draft.acting_type and draft.acting_name
        else draft.signatory.display_name if draft.signatory_id
        else institution.leader_name
    )
    _, configured_issue_code = p16_number_parts(draft.assignment)
    return {
        "signer_name": signer_name,
        "configured_issue_code": configured_issue_code,
        "sender": " ".join(filter(None, (
            draft.get_acting_type_display() if draft.acting_type else "",
            (institution.leader_title or f"KEPALA {institution.work_unit}").strip(),
        ))).upper(),
    }


def _resolved_metadata(targets, form_context, issue_code_target=None):
    signer_name = targets["signer_name"]
    signatory_id = match_option(
        form_context.get("penandatangan_options", []), signer_name, "Penanda tangan"
    )
    issue_code = match_option(
        form_context.get("kode_masalah_options", []),
        issue_code_target or targets["configured_issue_code"],
        "Kode masalah",
    )
    return {
        "signatory_id": signatory_id,
        "signatory_name": signer_name,
        "issue_code": issue_code,
        "sender": targets["sender"],
    }


def _persist_session(integration, session_data, context, form_context):
    session_data.update({
        "cookies": context.cookies([sipede.SIPEDE_BASE_URL]),
        "p16_create": form_context,
        "captured_url": P16_CREATE_URL,
        "captured_at": int(time.time()),
    })
    encrypted_payload, _connected_at = sipede.save_session_payload(integration.pk, session_data)
    integration.session_encrypted = encrypted_payload


def acquire_number(user, draft, *, sifat=P16_SIFAT, issue_code=None, signatory_name=None):
    if sifat not in P16_ALLOWED_SIFAT:
        raise P16SipedeError("Sifat surat P-16 tidak valid.")
    integration, session_data = _integration_and_session(user)
    metadata_targets = _metadata_targets(draft, signatory_name)
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser, context, page, form_context = _open_p16_form(playwright, session_data)
            metadata = _resolved_metadata(metadata_targets, form_context, issue_code)
            resolved_sifat = match_option(
                form_context.get("sifat_options", []), sifat, "Sifat surat"
            )
            headers = {
                "Accept": "*/*",
                "Referer": P16_CREATE_URL,
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-TOKEN": form_context["csrf_token"],
            }
            jenis_surat = form_context.get("jenis_surat") or P16_JENIS_SURAT
            auto_number_response = context.request.get(
                f"{sipede.SIPEDE_BASE_URL}/suratkeluar/check-auto-number",
                headers=headers,
                params={"surat": jenis_surat},
                timeout=120000,
            )
            if not auto_number_response.ok:
                raise P16SipedeError(
                    f"SIPede gagal memeriksa nomor otomatis (HTTP {auto_number_response.status})."
                )
            payload = {
                "_token": form_context["csrf_token"],
                "jenis_surat": jenis_surat,
                "bidang_main": form_context.get("bidang_main") or "",
                "tanggal": draft.letter_date.isoformat(),
                "sifat_surat": resolved_sifat,
                "penandatangan": metadata["signatory_id"],
            }
            response = context.request.post(
                f"{sipede.SIPEDE_BASE_URL}/getnosurat/cekno",
                headers=headers,
                form=payload,
                timeout=120000,
            )
            if not response.ok:
                raise P16SipedeError(f"SIPede menolak permintaan nomor surat (HTTP {response.status}).")
            number = response.text().strip().strip('"')
            if (
                not number or len(number) > 100 or "<html" in number.lower()
                or re.search(r"[\r\n]", number)
            ):
                raise P16SipedeError("Nomor sequence P-16 tidak diterima dari SIPede.")
            _persist_session(integration, session_data, context, form_context)
            return {"number": number, "sifat": resolved_sifat, **metadata}
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


def _render_pdf(playwright, document_html):
    encoded = (document_html or "").encode("utf-8")
    lowered = document_html.lower()
    blocked = ("<script", "<iframe", "<object", "<embed", "<link", "http://", "https://", "file:")
    if not encoded or len(encoded) > MAX_HTML_BYTES or any(token in lowered for token in blocked):
        raise P16SipedeError("Pratinjau P-16 tidak valid atau terlalu besar.")
    css_paths = (
        Path(settings.BASE_DIR, "static", "css", "p16-editor.css"),
        Path(settings.BASE_DIR, "static", "css", "p16-structured-editor.css"),
        Path(settings.BASE_DIR, "static", "css", "p16-document.css"),
    )
    styles = "\n".join(path.read_text(encoding="utf-8") for path in css_paths)
    launch_options = {"headless": True}
    chrome = sipede._chrome_executable()
    if chrome:
        launch_options["executable_path"] = str(chrome)
    browser = playwright.chromium.launch(**launch_options)
    try:
        context = browser.new_context(java_script_enabled=False)
        page = context.new_page()
        page.route("**/*", lambda route: route.abort())
        page.set_content(
            f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>html,body,*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}{styles}</style></head>"
            f"<body><div class='p16-preview-pages'>{document_html}</div></body></html>",
            wait_until="load",
        )
        page.emulate_media(media="print")
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
    finally:
        browser.close()
    if not pdf or len(pdf) > MAX_PDF_BYTES:
        raise P16SipedeError("PDF P-16 gagal dibuat atau ukurannya melebihi 18 MB.")
    return pdf


def render_document_pdf(document_html):
    """Render the current P-16 preview as a downloadable PDF."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        return _render_pdf(playwright, document_html)


def upload_document(
    user,
    draft,
    document_html,
    *,
    sifat=P16_SIFAT,
    issue_code=None,
    destination=P16_TUJUAN,
    subject=P16_PERIHAL,
    signatory_name=None,
    disposition_ids=None,
):
    if sifat not in P16_ALLOWED_SIFAT:
        raise P16SipedeError("Sifat surat P-16 tidak valid.")
    destination = (destination or "").strip()
    subject = (subject or "").strip()
    if not destination or len(destination) > 500:
        raise P16SipedeError("Tujuan surat P-16 wajib diisi dan maksimal 500 karakter.")
    if not subject or len(subject) > 500:
        raise P16SipedeError("Perihal surat P-16 wajib diisi dan maksimal 500 karakter.")
    number_pattern = re.compile(
        r'(<[^>]+data-p16-output=["\']number["\'][^>]*>).*?(</[^>]+>)',
        re.IGNORECASE | re.DOTALL,
    )
    document_html, number_count = number_pattern.subn(
        lambda match: f"{match.group(1)}{draft.draft_number}{match.group(2)}",
        document_html or "",
    )
    if not draft.draft_number or number_count < 1:
        raise P16SipedeError(
            "Bagian nomor surat tidak ditemukan pada dokumen P-16. Muat ulang halaman lalu coba kembali."
        )
    disposition_ids = [str(value).strip() for value in (disposition_ids or [])]
    if not disposition_ids or any(not value.isdigit() for value in disposition_ids):
        raise P16SipedeError("Pilih minimal satu tujuan disposisi sebelum P-16 dikirim.")
    integration, session_data = _integration_and_session(user)
    metadata_targets = _metadata_targets(draft, signatory_name)
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            pdf = _render_pdf(playwright, document_html)
            browser, context, page, form_context = _open_p16_form(playwright, session_data)
            metadata = _resolved_metadata(metadata_targets, form_context, issue_code)
            resolved_sifat = match_option(
                form_context.get("sifat_options", []), sifat, "Sifat surat"
            )
            multipart = {
                "_token": form_context["csrf_token"],
                "nomor": draft.draft_number,
                "tanggal": draft.letter_date.isoformat(),
                "sifat": resolved_sifat,
                "kode_masalah": metadata["issue_code"],
                "dari": metadata["sender"],
                "tujuan": destination,
                "hal": subject,
                "penandatangan": metadata["signatory_id"],
                "idSurat": form_context.get("id_surat") or P16_ID_SURAT,
                "tujuan_surat": ",".join(disposition_ids),
                "submitModal": "ok",
                "src": {"name": f"P-16-{draft.pk}.pdf", "mimeType": "application/pdf", "buffer": pdf},
            }
            response = context.request.post(
                form_context["form_action"],
                headers={"Accept": "text/html,application/xhtml+xml", "Referer": P16_CREATE_URL},
                multipart=multipart,
                timeout=120000,
            )
            if not response.ok:
                raise P16SipedeError(f"SIPede menolak upload P-16 (HTTP {response.status}).")
            response_text = response.text()
            response_path = urlparse(response.url).path.rstrip("/")
            if response_path.endswith("/create") and "formCreateEdit" in response_text:
                match = re.search(
                    r'class=["\'][^"\']*(?:alert-danger|invalid-feedback|text-danger)[^"\']*["\'][^>]*>(.*?)<',
                    response_text,
                    re.IGNORECASE | re.DOTALL,
                )
                detail = re.sub(r"<[^>]+>", " ", match.group(1)).strip() if match else ""
                raise P16SipedeError(detail or "SIPede belum menerima data dan PDF P-16.")
            _persist_session(integration, session_data, context, form_context)
            return {"number": draft.draft_number, **metadata}
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
