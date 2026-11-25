"""Pengambilan nomor dan upload P-17 ke Administrasi Perkara SIPede."""

import re
import time
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from configurations import sipede
from configurations.models import InstitutionConfiguration
from .p17_numbering import p17_number_parts
from .sipede_p16 import (
    MAX_HTML_BYTES, MAX_PDF_BYTES, P16_ALLOWED_SIFAT,
    P16SipedeError, P16SipedeLoginRequired, _integration_and_session,
    _read_form_context, _restore_cookies, _signatory_name_tokens,
    match_option, match_signatory_option,
)

P17SipedeError = P16SipedeError
P17SipedeLoginRequired = P16SipedeLoginRequired
P17_CREATE_URL = f"{sipede.SIPEDE_BASE_URL}/administrasiperkara/create?idSurat=7"
P17_DISPOSITION_OPTIONS_URL = f"{sipede.SIPEDE_BASE_URL}/suratkeluar/get-master-tujuan-disposisi"
P17_ID_SURAT = "7"
P17_SIFAT = "B"


def _close_browser(browser):
    """Tutup browser sebelum Playwright berhenti tanpa menutupi hasil proses utama."""
    if not browser:
        return
    try:
        browser.close()
    except Exception:
        pass


def _open_form(
    playwright, session_data, *, id_surat=P17_ID_SURAT,
    document_label="P-17", form_route="administrasiperkara",
):
    if form_route not in {"administrasiperkara", "suratkeluar"}:
        raise P17SipedeError("Rute formulir SIPede tidak dikenal.")
    form_title = "Surat Keluar" if form_route == "suratkeluar" else "Administrasi Perkara"
    create_url = f"{sipede.SIPEDE_BASE_URL}/{form_route}/create?idSurat={id_surat}"
    browser, context, page = sipede._open_browser(playwright, use_proxy=True)
    _restore_cookies(context, session_data)
    page.goto(create_url, wait_until="domcontentloaded", timeout=60000)
    if "/login" in urlparse(page.url).path.lower():
        browser.close()
        raise P17SipedeLoginRequired("Sesi SIPede telah kedaluwarsa. Silakan login ulang.")
    try:
        page.locator("#formCreateEdit").wait_for(state="attached", timeout=30000)
    except Exception as exc:
        browser.close()
        raise P17SipedeError(f"Formulir {form_title} {document_label} tidak ditemukan di SIPede.") from exc
    form_context = _read_form_context(page)
    action = urlparse(form_context.get("form_action") or "")
    if (
        not form_context.get("csrf_token")
        or action.scheme != "https"
        or action.hostname != "sipede.kejaksaan.go.id"
        or action.path.rstrip("/") != f"/{form_route}"
    ):
        browser.close()
        raise P17SipedeError(f"Token atau alamat formulir {form_title} {document_label} SIPede tidak valid.")
    form_context["id_surat"] = str(id_surat)
    form_context["create_url"] = create_url
    form_context["form_route"] = form_route
    return browser, context, page, form_context


def _persist(integration, session_data, context, form_context, cache_key="p17_create"):
    session_data.update({
        "cookies": context.cookies([sipede.SIPEDE_BASE_URL]),
        cache_key: form_context, "captured_url": form_context.get("create_url", P17_CREATE_URL),
        "captured_at": int(time.time()),
    })
    encrypted, _ = sipede.save_session_payload(integration.pk, session_data)
    integration.session_encrypted = encrypted


def _metadata_targets(draft, signatory_name=None):
    """Baca seluruh data Django sebelum event loop internal Playwright aktif."""
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    signer = (signatory_name or institution.leader_name or "").strip()
    _, configured_code = p17_number_parts(draft.spdp)
    return {
        "signatory_name": signer,
        "configured_issue_code": configured_code,
        "sender": (institution.leader_title or f"KEPALA {institution.work_unit}").strip().upper(),
    }


def _resolved_metadata(targets, form_context, issue_code=None):
    """Cocokkan data lokal dengan opsi form SIPede tanpa mengakses ORM."""
    return {
        "signatory_id": match_signatory_option(
            form_context.get("penandatangan_options", []),
            targets["signatory_name"],
        ),
        "signatory_name": targets["signatory_name"],
        "issue_code": match_option(
            form_context.get("kode_masalah_options", []),
            issue_code or targets["configured_issue_code"],
            "Kode masalah",
        ),
        "sender": targets["sender"],
    }


def _suratkeluar_signatory_options(context, form_context, query, document_label):
    query = (query or "").strip()
    if not query:
        raise P17SipedeError(f"Penanda tangan {document_label} wajib dipilih.")
    response = context.request.get(
        f"{sipede.SIPEDE_BASE_URL}/suratkeluar/list-penandatangan-ajax",
        headers={
            "Accept": "application/json",
            "Referer": form_context["create_url"],
            "X-Requested-With": "XMLHttpRequest",
        },
        params={"q": query},
        timeout=120000,
    )
    if not response.ok:
        raise P17SipedeError(
            f"Daftar penanda tangan {document_label} gagal dimuat dari SIPede (HTTP {response.status})."
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise P17SipedeError(
            f"Respons daftar penanda tangan {document_label} dari SIPede tidak valid."
        ) from exc
    rows = payload.get("results", payload.get("data", [])) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise P17SipedeError(
            f"Format daftar penanda tangan {document_label} dari SIPede tidak valid."
        )
    options = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = str(row.get("id") or row.get("value") or "").strip()
        label = str(row.get("text") or row.get("label") or row.get("nama") or "").strip()
        if value and label:
            options.append({"value": value, "label": label})
    return options


def _signatory_search_queries(value):
    value = (value or "").strip()
    name = " ".join(_signatory_name_tokens(value))
    return list(dict.fromkeys(query for query in (value, name) if query))


def _resolved_form_metadata(
    context, targets, form_context, issue_code, document_label, form_route,
):
    if form_route == "suratkeluar":
        form_context = dict(form_context)
        options = []
        for query in _signatory_search_queries(targets["signatory_name"]):
            options = _suratkeluar_signatory_options(
                context, form_context, query, document_label,
            )
            if not options:
                continue
            try:
                match_signatory_option(options, targets["signatory_name"])
            except P17SipedeError as exc:
                if "lebih dari satu opsi" in str(exc):
                    raise
                continue
            break
        else:
            raise P17SipedeError(
                f"Penanda tangan '{targets['signatory_name']}' tidak ditemukan pada formulir SIPede."
            )
        form_context["penandatangan_options"] = options
    return _resolved_metadata(targets, form_context, issue_code)


def _resolve_sipede_jenis(form_context, jenis_surat, document_label, form_route):
    if form_route == "suratkeluar":
        if not jenis_surat:
            raise P17SipedeError(f"Jenis surat {document_label} belum dikonfigurasi.")
        return match_option(form_context.get("jenis_options", []), jenis_surat, "Jenis surat")
    return form_context.get("jenis_surat") or form_context.get("jenis") or ""


def session_available(
    user, *, id_surat=P17_ID_SURAT, document_label="P-17",
    form_route="administrasiperkara",
):
    integration, session_data = _integration_and_session(user)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = None
        try:
            browser, context, _page, form_context = _open_form(
                playwright, session_data, id_surat=id_surat,
                document_label=document_label, form_route=form_route,
            )
            _persist(integration, session_data, context, form_context, f"document_{id_surat}_create")
            return True
        finally:
            _close_browser(browser)


def disposition_options(
    user, *, id_surat=P17_ID_SURAT, document_label="P-17",
    form_route="administrasiperkara",
):
    integration, session_data = _integration_and_session(user)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = None
        try:
            browser, context, _page, form_context = _open_form(
                playwright, session_data, id_surat=id_surat,
                document_label=document_label, form_route=form_route,
            )
            response = context.request.get(P17_DISPOSITION_OPTIONS_URL, headers={"Accept": "application/json", "Referer": form_context["create_url"]}, timeout=120000)
            if not response.ok:
                raise P17SipedeError(f"Daftar tujuan disposisi SIPede gagal dimuat (HTTP {response.status}).")
            payload = response.json()
            options = []
            for row in payload.get("data", []) if isinstance(payload, dict) else []:
                value = str(row.get("id_tujuan_penerusan", "")).strip()
                if value.isdigit():
                    users = row.get("user") if isinstance(row.get("user"), list) else []
                    name = str(users[0].get("nama", "")).strip() if users and isinstance(users[0], dict) else ""
                    options.append({"value": value, "label": f"{row.get('nama_jabatan', '')} ({name or 'NO USER'})".strip()})
            _persist(integration, session_data, context, form_context, f"document_{id_surat}_create")
            return options
        finally:
            _close_browser(browser)


def acquire_number(
    user, draft, *, sifat=P17_SIFAT, issue_code=None, signatory_name=None,
    id_surat=P17_ID_SURAT, document_label="P-17",
    form_route="administrasiperkara", jenis_surat=None,
):
    if sifat not in P16_ALLOWED_SIFAT:
        raise P17SipedeError(f"Sifat surat {document_label} tidak valid.")
    integration, session_data = _integration_and_session(user)
    metadata_targets = _metadata_targets(draft, signatory_name)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = None
        try:
            browser, context, _page, form_context = _open_form(
                playwright, session_data, id_surat=id_surat,
                document_label=document_label, form_route=form_route,
            )
            metadata = _resolved_form_metadata(
                context, metadata_targets, form_context, issue_code,
                document_label, form_route,
            )
            resolved_sifat = match_option(form_context.get("sifat_options", []), sifat, "Sifat surat")
            jenis = _resolve_sipede_jenis(
                form_context, jenis_surat, document_label, form_route,
            )
            if not jenis:
                raise P17SipedeError(f"Jenis surat {document_label} tidak ditemukan pada formulir SIPede.")
            headers = {"Accept": "*/*", "Referer": form_context["create_url"], "X-Requested-With": "XMLHttpRequest", "X-CSRF-TOKEN": form_context["csrf_token"]}
            if form_route == "suratkeluar":
                auto_number_response = context.request.get(
                    f"{sipede.SIPEDE_BASE_URL}/suratkeluar/check-auto-number",
                    headers=headers,
                    params={"surat": jenis},
                    timeout=120000,
                )
                if not auto_number_response.ok:
                    raise P17SipedeError(
                        f"SIPede gagal memeriksa nomor otomatis {document_label} (HTTP {auto_number_response.status})."
                    )
            response = context.request.post(f"{sipede.SIPEDE_BASE_URL}/getnosurat/cekno", headers=headers, form={
                "_token": form_context["csrf_token"], "jenis_surat": jenis,
                "bidang_main": form_context.get("bidang_main") or "", "tanggal": draft.letter_date.isoformat(),
                "sifat_surat": resolved_sifat, "penandatangan": metadata["signatory_id"],
            }, timeout=120000)
            if not response.ok:
                raise P17SipedeError(f"SIPede menolak permintaan nomor {document_label} (HTTP {response.status}).")
            number = response.text().strip().strip('"')
            if not number or len(number) > 100 or "<html" in number.lower() or re.search(r"[\r\n]", number):
                raise P17SipedeError(f"Nomor sequence {document_label} tidak diterima dari SIPede.")
            _persist(integration, session_data, context, form_context, f"document_{id_surat}_create")
            return {
                "number": number,
                "sifat": resolved_sifat,
                "jenis_surat": jenis,
                **metadata,
            }
        finally:
            _close_browser(browser)


def _render_pdf(playwright, document_html, document_label="P-17"):
    encoded = (document_html or "").encode("utf-8")
    blocked = ("<script", "<iframe", "<object", "<embed", "<link", "http://", "https://", "file:")
    if not encoded or len(encoded) > MAX_HTML_BYTES or any(token in (document_html or "").lower() for token in blocked):
        raise P17SipedeError(f"Pratinjau {document_label} tidak valid atau terlalu besar.")
    if document_label == "P-17": css_names = ("p17-editor.css", "p17-document.css", "standard-letterhead.css")
    elif document_label == "P-21": css_names = ("p21-editor.css", "p21-document.css", "standard-letterhead.css")
    elif document_label.startswith("SOP Form 2") or document_label.startswith("SOP Form 3"): css_names = ("sop-form-document.css", "sop-form-02-layout.css", "standard-letterhead.css")
    else: css_names = ("case-document-editor.css", "case-document.css", "standard-letterhead.css", "p19-editor.css", "p20-editor.css")
    css_paths = [Path(settings.BASE_DIR, "static", "css", name) for name in css_names]
    styles = "\n".join(path.read_text(encoding="utf-8") for path in css_paths)
    options = {"headless": True}
    chrome = sipede._chrome_executable()
    if chrome:
        options["executable_path"] = str(chrome)
    browser = playwright.chromium.launch(**options)
    try:
        page = browser.new_context(java_script_enabled=False).new_page()
        page.route("**/*", lambda route: route.abort())
        wrapper = "p17-preview-pages" if document_label == "P-17" else "sop-print-document"
        page.set_content(f"<!doctype html><html><head><meta charset='utf-8'><style>html,body,*{{box-sizing:border-box}}html,body{{margin:0;padding:0}}{styles}</style></head><body><div class='{wrapper}'>{document_html}</div></body></html>", wait_until="load")
        page.emulate_media(media="print")
        pdf = page.pdf(prefer_css_page_size=True, print_background=True)
    finally:
        browser.close()
    if not pdf or len(pdf) > MAX_PDF_BYTES:
        raise P17SipedeError(f"PDF {document_label} gagal dibuat atau ukurannya melebihi 18 MB.")
    return pdf


def render_document_pdf(document_html, document_label="P-17"):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        return _render_pdf(playwright, document_html, document_label)


def upload_document(
    user, draft, document_html, *, sifat=P17_SIFAT, issue_code=None,
    destination="", subject="", signatory_name=None, disposition_ids=None,
    id_surat=P17_ID_SURAT, document_label="P-17",
    form_route="administrasiperkara", jenis_surat=None,
):
    destination, subject = (destination or "").strip(), (subject or "").strip()
    if not destination or not subject:
        raise P17SipedeError(f"Tujuan dan perihal {document_label} wajib diisi.")
    if document_label == "P-17": output_attr = "data-p17-output"
    elif document_label == "P-21": output_attr = "data-p21-output"
    elif document_label.startswith("SOP Form 2") or document_label.startswith("SOP Form 3"): output_attr = "data-sop-output"
    else: output_attr = "data-document-output"
    pattern = re.compile(rf'(<[^>]+{output_attr}=["\']number["\'][^>]*>).*?(</[^>]+>)', re.I | re.S)
    document_html, count = pattern.subn(lambda m: f"{m.group(1)}{draft.letter_number}{m.group(2)}", document_html or "")
    if not draft.letter_number or count < 1:
        raise P17SipedeError(f"Bagian nomor surat tidak ditemukan pada dokumen {document_label}.")
    dispositions = [str(value).strip() for value in (disposition_ids or [])]
    if not dispositions or any(not value.isdigit() for value in dispositions):
        raise P17SipedeError(f"Pilih minimal satu tujuan disposisi sebelum {document_label} dikirim.")
    integration, session_data = _integration_and_session(user)
    metadata_targets = _metadata_targets(draft, signatory_name)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = None
        try:
            pdf = _render_pdf(playwright, document_html, document_label)
            browser, context, _page, form_context = _open_form(
                playwright, session_data, id_surat=id_surat,
                document_label=document_label, form_route=form_route,
            )
            metadata = _resolved_form_metadata(
                context, metadata_targets, form_context, issue_code,
                document_label, form_route,
            )
            resolved_sifat = match_option(form_context.get("sifat_options", []), sifat, "Sifat surat")
            resolved_jenis = _resolve_sipede_jenis(
                form_context, jenis_surat, document_label, form_route,
            )
            pdf_part = {
                "name": f"{document_label.replace(' ', '-')}-{draft.pk}.pdf",
                "mimeType": "application/pdf",
                "buffer": pdf,
            }
            multipart = {
                "_token": form_context["csrf_token"], "nomor": draft.letter_number,
                "tanggal": draft.letter_date.isoformat(), "sifat": resolved_sifat,
                "kode_masalah": metadata["issue_code"], "dari": metadata["sender"],
                "tujuan": destination, "hal": subject, "penandatangan": metadata["signatory_id"],
                "idSurat": str(id_surat), "tujuan_surat": ",".join(dispositions), "submitModal": "ok",
            }
            if form_route == "suratkeluar":
                multipart["jenis"] = resolved_jenis
                multipart["upload"] = pdf_part
            else:
                multipart["src"] = pdf_part
                multipart["lampiran"] = {
                    "name": "", "mimeType": "application/octet-stream", "buffer": b"",
                }
            response = context.request.post(
                form_context["form_action"],
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "Referer": form_context["create_url"],
                },
                multipart=multipart,
                timeout=120000,
            )
            if not response.ok:
                raise P17SipedeError(f"SIPede menolak upload {document_label} (HTTP {response.status}).")
            if urlparse(response.url).path.rstrip("/").endswith("/create") and "formCreateEdit" in response.text():
                raise P17SipedeError(f"SIPede belum menerima data dan PDF {document_label}.")
            _persist(integration, session_data, context, form_context, f"document_{id_surat}_create")
            return {"number": draft.letter_number, "jenis_surat": resolved_jenis, **metadata}
        finally:
            _close_browser(browser)
