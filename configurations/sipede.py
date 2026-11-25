"""Login SIPede melalui Chrome dan penyimpanan sesi terenkripsi."""

import base64
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlparse
import uuid
from concurrent.futures import ThreadPoolExecutor

from cryptography.fernet import Fernet
from django.conf import settings
from django.utils import timezone

from .models import SipedeIntegration

SIPEDE_LOGIN_URL = "https://sipede.kejaksaan.go.id/login"
SIPEDE_BASE_URL = "https://sipede.kejaksaan.go.id"
SIPEDE_SURATKELUAR_CREATE_URL = f"{SIPEDE_BASE_URL}/suratkeluar/create?idSurat=125"
DEFAULT_CHROME_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
)
_sessions = {}
_lock = threading.Lock()


def _cipher():
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest())
    return Fernet(key)


def encrypt(value):
    return _cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value):
    return _cipher().decrypt(value.encode("ascii")).decode("utf-8")


def _chrome_executable():
    configured = os.getenv("CHROME_EXECUTABLE", "").strip()
    candidates = ((Path(configured),) if configured else ()) + DEFAULT_CHROME_PATHS
    return next((path for path in candidates if path.is_file()), None)


def _browser_args(use_proxy=True):
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=BlockInsecurePrivateNetworkRequests",
        "--incognito",
    ]
    if use_proxy:
        proxy_server = (
            os.getenv("SIPEDE_BROWSER_PROXY_SERVER", "").strip()
            or os.getenv("BROWSER_PROXY_SERVER", "").strip()
        )
        proxy_bypass = (
            os.getenv("SIPEDE_BROWSER_PROXY_BYPASS", "").strip()
            or os.getenv("BROWSER_PROXY_BYPASS", "").strip()
        )
        use_system_proxy = os.getenv("SIPEDE_BROWSER_USE_SYSTEM_PROXY", "1") == "1"
        if proxy_server:
            args.append(f"--proxy-server={proxy_server}")
        elif not use_system_proxy:
            args.append("--no-proxy-server")
        if proxy_bypass:
            args.append(f"--proxy-bypass-list={proxy_bypass}")
    else:
        args.append("--no-proxy-server")
    return args


def _friendly_error(error):
    detail = str(error)
    if "ERR_NETWORK_ACCESS_DENIED" in detail:
        return (
            "Akses jaringan Chrome ke SIPede ditolak. Sistem sudah mencoba proxy Windows "
            "dan koneksi langsung. Izinkan Google Chrome pada Firewall/antivirus, lalu coba lagi."
        )
    if "ERR_PROXY_CONNECTION_FAILED" in detail:
        return "Proxy Windows tidak dapat digunakan untuk membuka SIPede. Periksa pengaturan proxy lalu coba lagi."
    if "ERR_NAME_NOT_RESOLVED" in detail:
        return "Alamat SIPede tidak ditemukan oleh DNS. Periksa koneksi internet atau DNS komputer server."
    if "ERR_CONNECTION_TIMED_OUT" in detail or "Timeout" in detail or "timeout" in detail:
        return "Koneksi ke SIPede melewati batas waktu. Periksa internet lalu coba lagi."
    if "ERR_INTERNET_DISCONNECTED" in detail:
        return "Komputer server tidak terhubung ke internet. Sambungkan jaringan lalu coba lagi."
    if "Executable doesn't exist" in detail:
        return "Browser untuk koneksi SIPede belum tersedia. Pasang Google Chrome lalu coba lagi."
    return detail[:500] or "Koneksi SIPede gagal karena kesalahan yang tidak diketahui."


def state_for(user_id, auth_id):
    with _lock:
        state = _sessions.get(auth_id)
        return state.copy() if state and state["user_id"] == user_id else None


def start(user_id):
    integration = SipedeIntegration.objects.filter(user_id=user_id).first()
    if not integration:
        raise ValueError("Simpan username dan password SIPede terlebih dahulu.")
    auth_id = uuid.uuid4().hex
    with _lock:
        _sessions[auth_id] = {
            "user_id": user_id,
            "status": "starting",
            "message": "Menyiapkan Google Chrome di komputer server…",
            "captcha": "",
            "captcha_input": "",
            "cancelled": False,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
    threading.Thread(
        target=_run_login,
        args=(auth_id, integration.pk),
        daemon=True,
        name=f"sipede-login-{user_id}",
    ).start()
    return auth_id


def submit_captcha(user_id, auth_id, value):
    if not value or len(value) > 32:
        raise ValueError("Kode CAPTCHA tidak valid.")
    with _lock:
        state = _sessions.get(auth_id)
        if not state or state["user_id"] != user_id or state["status"] != "captcha":
            raise ValueError("Sesi CAPTCHA tidak tersedia atau telah berakhir.")
        state.update(
            status="loading",
            message="Memverifikasi CAPTCHA…",
            captcha_input=value,
            updated_at=time.time(),
        )


def cancel(user_id, auth_id):
    with _lock:
        state = _sessions.get(auth_id)
        if not state or state["user_id"] != user_id:
            raise ValueError("Sesi koneksi SIPede tidak ditemukan.")
        state.update(
            cancelled=True,
            status="cancelled",
            message="Koneksi SIPede dibatalkan.",
            captcha="",
            updated_at=time.time(),
        )


def _update(auth_id, **values):
    with _lock:
        if auth_id in _sessions and not _sessions[auth_id].get("cancelled"):
            _sessions[auth_id].update(values, updated_at=time.time())


def _wait_for_captcha(auth_id, seconds=600):
    deadline = time.time() + seconds
    while time.time() < deadline:
        with _lock:
            state = _sessions.get(auth_id)
            if not state or state.get("cancelled"):
                return None
            value = state.pop("captcha_input", "")
        if value:
            return value
        time.sleep(0.25)
    raise RuntimeError("Waktu memasukkan CAPTCHA habis. Silakan hubungkan ulang SIPede.")


def _open_browser(playwright, use_proxy=True):
    launch_options = {
        "headless": os.getenv("SIPEDE_BROWSER_HEADLESS", "1") == "1",
        "slow_mo": int(os.getenv("SIPEDE_BROWSER_SLOW_MO", "150")),
        "args": _browser_args(use_proxy=use_proxy),
    }
    chrome = _chrome_executable()
    if chrome:
        launch_options["executable_path"] = str(chrome)
    browser = playwright.chromium.launch(**launch_options)
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="id-ID")
    return browser, context, context.new_page()


def _session_payload(context, page, create_context=None):
    try:
        local_storage = page.evaluate(
            "Object.fromEntries(Array.from({length: localStorage.length}, (_, i) => "
            "[localStorage.key(i), localStorage.getItem(localStorage.key(i))]))"
        )
    except Exception:
        local_storage = {}
    return {
        "cookies": context.cookies([SIPEDE_BASE_URL]),
        "local_storage": local_storage,
        "suratkeluar_create": create_context or {},
        "captured_url": page.url,
        "captured_at": int(time.time()),
    }


def _read_create_context(page):
    return page.evaluate("""() => {
        const form = document.querySelector('#formCreateEdit') ||
            document.querySelector('form[action$="/suratkeluar"]');
        const optionsOf = (name) => Array.from(document.querySelectorAll(`[name="${name}"] option`))
            .map(option => ({value: option.value, label: option.textContent.trim()}))
            .filter(option => option.value);
        const valueOf = (name) => document.querySelector(`[name="${name}"]`)?.value || '';
        return {
            csrf_token: valueOf('_token') || document.querySelector('meta[name="csrf-token"]')?.content || '',
            form_action: form?.action || 'https://sipede.kejaksaan.go.id/suratkeluar',
            form_method: (form?.method || 'post').toUpperCase(),
            form_enctype: form?.enctype || 'multipart/form-data',
            id_surat: valueOf('idSurat') || '125',
            jenis_options: optionsOf('jenis'),
            sifat_options: optionsOf('sifat'),
            kode_masalah_options: optionsOf('kode_masalah'),
            penandatangan_options: optionsOf('penandatangan'),
            field_names: form ? Array.from(form.elements).map(field => field.name).filter(Boolean) : []
        };
    }""")


def _update_session_record(integration_id, encrypted_payload, connected_at):
    """Jalankan ORM pada thread biasa, terpisah dari event loop internal Playwright."""
    from django.db import close_old_connections

    close_old_connections()
    try:
        SipedeIntegration.objects.filter(pk=integration_id).update(
            session_encrypted=encrypted_payload,
            connected_at=connected_at,
            updated_at=connected_at,
        )
    finally:
        close_old_connections()


def save_session_payload(integration_id, payload, *, mark_connected=True):
    encrypted_payload = encrypt(json.dumps(payload, ensure_ascii=False))
    connected_at = timezone.now()
    # Playwright sync API menjalankan event loop internal. Django melarang ORM
    # langsung dari konteks itu, jadi penulisan sesi dilakukan pada worker sync.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="sipede-db") as executor:
        executor.submit(
            _update_session_record, integration_id, encrypted_payload, connected_at
        ).result()
    return encrypted_payload, connected_at


def _save_session(integration, payload):
    encrypted_payload, connected_at = save_session_payload(integration.pk, payload)
    integration.session_encrypted = encrypted_payload
    integration.connected_at = connected_at


def _run_login(auth_id, integration_id):
    browser = None
    try:
        from playwright.sync_api import sync_playwright

        integration = SipedeIntegration.objects.get(pk=integration_id)
        password = decrypt(integration.password_encrypted)
        with sync_playwright() as playwright:
            browser, context, page = _open_browser(playwright, use_proxy=True)
            _update(auth_id, status="loading", message="Membuka halaman login SIPede…")
            try:
                page.goto(SIPEDE_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            except Exception as first_error:
                error_text = str(first_error)
                if not any(code in error_text for code in ("ERR_NETWORK_ACCESS_DENIED", "ERR_PROXY_CONNECTION_FAILED")):
                    raise
                _update(auth_id, status="loading", message="Akses melalui proxy gagal. Mencoba koneksi langsung…")
                try:
                    browser.close()
                except Exception:
                    pass
                browser, context, page = _open_browser(playwright, use_proxy=False)
                page.goto(SIPEDE_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

            authenticated = False
            for attempt in range(3):
                page.locator("#username, input[name='username'], input[type='text']").first.fill(integration.username)
                page.locator("input[name='password'], input[type='password']").first.fill(password)
                captcha_image = page.locator(".captcha img, img[src*='captcha' i], img[alt*='captcha' i]").first
                captcha_image.wait_for(state="visible", timeout=30000)
                captcha_data = base64.b64encode(captcha_image.screenshot(type="png")).decode("ascii")
                _update(
                    auth_id,
                    status="captcha",
                    message=("Masukkan kode CAPTCHA SIPede yang tampil."
                             if attempt == 0 else "Login belum diterima. Masukkan CAPTCHA baru."),
                    captcha=f"data:image/png;base64,{captcha_data}",
                    attempt=attempt + 1,
                )
                captcha_value = _wait_for_captcha(auth_id)
                if captcha_value is None:
                    return
                page.locator("#captcha, input[name*='captcha' i], input[placeholder*='captcha' i]").first.fill(captcha_value)
                page.locator("form[action*='login-post'] button[type='submit'], button[type='submit'], input[type='submit']").first.click()
                try:
                    page.wait_for_function(
                        "() => !location.pathname.replace(/\\/$/, '').endsWith('/login')",
                        timeout=30000,
                    )
                except Exception:
                    page.wait_for_timeout(1200)
                if "/login" not in urlparse(page.url).path.lower():
                    authenticated = True
                    break

            if not authenticated:
                raise RuntimeError("Login SIPede belum berhasil. Periksa CAPTCHA, username, atau password.")

            payload = _session_payload(context, page)
            if not payload["cookies"]:
                raise RuntimeError("Halaman SIPede terbuka, tetapi cookie sesi tidak ditemukan.")
            _save_session(integration, payload)

            _update(auth_id, status="loading", captcha="", message="Sesi tersimpan. Membaca formulir Surat Keluar…")
            try:
                page.goto(SIPEDE_SURATKELUAR_CREATE_URL, wait_until="domcontentloaded", timeout=60000)
                page.locator("#formCreateEdit, form[action$='/suratkeluar']").first.wait_for(
                    state="attached", timeout=30000
                )
                payload = _session_payload(context, page, _read_create_context(page))
                _save_session(integration, payload)
            except Exception:
                pass

            _update(
                auth_id,
                status="success",
                message="SIPede berhasil terhubung. Cookie dan sesi telah disimpan terenkripsi.",
                captcha="",
            )
    except Exception as exc:
        _update(auth_id, status="error", message=_friendly_error(exc), captcha="")
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
