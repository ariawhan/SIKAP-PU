"""Login CMS melalui HTTP biasa dan penyimpanan cookie sesi terenkripsi."""

import json
import re
import socket
from html import unescape
from http.cookiejar import Cookie, CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from django.utils import timezone

from .models import CMSIntegration, CMSServiceConfiguration
from .sipede import decrypt, encrypt


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
)
TIMEOUT = 20


def _base_url():
    config = CMSServiceConfiguration.objects.first()
    value = (config.base_url if config else "").strip().rstrip("/")
    if not value:
        raise ValueError("Alamat CMS belum dikonfigurasi oleh Admin.")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Alamat CMS tidak valid.")
    return value


def _request(opener, url, *, data=None, referer=""):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.7,en;q=0.6",
        "Cache-Control": "no-cache",
    }
    if referer:
        headers["Referer"] = referer
    encoded = urlencode(data).encode("utf-8") if data is not None else None
    if encoded is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    response = opener.open(Request(url, data=encoded, headers=headers), timeout=TIMEOUT)
    return response, response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def _csrf_from_html(content):
    match = re.search(
        r'<input[^>]+name=["\']_csrf["\'][^>]+value=["\']([^"\']+)',
        content,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r'<meta[^>]+name=["\']csrf-token["\'][^>]+content=["\']([^"\']+)',
            content,
            flags=re.IGNORECASE,
        )
    if not match:
        raise ValueError("Token keamanan halaman login CMS tidak ditemukan.")
    return match.group(1)


def _is_login_page(url, content):
    return "/user/login" in urlparse(url).path.lower() or 'id="login-form"' in content.lower()


def _cookie_payload(jar, base_url):
    return {
        "base_url": base_url,
        "cookies": [
            {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "secure": cookie.secure,
                "expires": cookie.expires,
            }
            for cookie in jar
        ],
        "captured_at": int(timezone.now().timestamp()),
    }


def _jar_from_payload(payload):
    jar = CookieJar()
    for item in payload.get("cookies", []):
        jar.set_cookie(Cookie(
            version=0,
            name=item["name"],
            value=item["value"],
            port=None,
            port_specified=False,
            domain=item.get("domain") or urlparse(payload.get("base_url", "")).hostname or "",
            domain_specified=bool(item.get("domain")),
            domain_initial_dot=(item.get("domain") or "").startswith("."),
            path=item.get("path") or "/",
            path_specified=True,
            secure=bool(item.get("secure")),
            expires=item.get("expires"),
            discard=item.get("expires") is None,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        ))
    return jar


def session_is_valid(integration):
    if not integration.session_encrypted:
        return False
    try:
        payload = json.loads(decrypt(integration.session_encrypted))
        base_url = _base_url()
        if payload.get("base_url") != base_url:
            return False
        jar = _jar_from_payload(payload)
        response, content = _request(build_opener(HTTPCookieProcessor(jar)), base_url + "/")
        return not _is_login_page(response.geturl(), content)
    except Exception:
        return False


def connect(user_id, *, reuse_valid=True):
    integration = CMSIntegration.objects.filter(user_id=user_id).first()
    if not integration:
        raise ValueError("Simpan username dan password CMS terlebih dahulu.")
    if reuse_valid and session_is_valid(integration):
        return {"reused": True, "message": "Sesi CMS masih aktif dan siap digunakan."}

    base_url = _base_url()
    login_url = urljoin(base_url + "/", "user/login")
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))
    try:
        _response, login_html = _request(opener, login_url, referer=base_url + "/")
        csrf_token = _csrf_from_html(login_html)
        response, content = _request(opener, login_url, data={
            "_csrf": csrf_token,
            "login-form[login]": integration.username,
            "login-form[password]": decrypt(integration.password_encrypted),
            "login-form[rememberMe]": "0",
            "login-button": "",
        }, referer=login_url)
    except (HTTPError, URLError, TimeoutError, socket.timeout) as exc:
        raise ValueError(f"CMS tidak dapat dihubungi: {getattr(exc, 'reason', exc)}") from exc

    if _is_login_page(response.geturl(), content):
        raise ValueError("Login CMS gagal. Periksa username atau password.")
    payload = _cookie_payload(jar, base_url)
    if not any(item["name"] == "PHPSESSID" for item in payload["cookies"]):
        raise ValueError("Login berhasil, tetapi cookie sesi CMS tidak ditemukan.")
    now = timezone.now()
    CMSIntegration.objects.filter(pk=integration.pk).update(
        session_encrypted=encrypt(json.dumps(payload, ensure_ascii=False)),
        connected_at=now,
        updated_at=now,
    )
    return {"reused": False, "message": "CMS berhasil terhubung. Cookie sesi disimpan terenkripsi."}


def _load_session(integration):
    try:
        payload = json.loads(decrypt(integration.session_encrypted))
    except Exception as exc:
        raise ValueError("Data sesi CMS tidak dapat dibaca. Silakan login ulang.") from exc
    return payload, _jar_from_payload(payload)


def _store_session(integration, jar, base_url):
    payload = _cookie_payload(jar, base_url)
    CMSIntegration.objects.filter(pk=integration.pk).update(
        session_encrypted=encrypt(json.dumps(payload, ensure_ascii=False)),
    )


def open_spdp_create(user_id):
    """Pastikan login aktif lalu buka formulir Tambah SPDP dengan cookie tersimpan."""
    integration = CMSIntegration.objects.filter(user_id=user_id).first()
    if not integration:
        raise ValueError("Simpan username dan password CMS terlebih dahulu.")
    session_reused = bool(integration.session_encrypted)
    if not session_reused:
        connect(user_id, reuse_valid=False)
        integration.refresh_from_db()
    base_url = _base_url()
    target_url = urljoin(base_url + "/", "pidum/spdp/create")
    referer = urljoin(base_url + "/", "pidum/spdp/index")

    for attempt in range(2):
        payload, jar = _load_session(integration)
        opener = build_opener(HTTPCookieProcessor(jar))
        try:
            response, content = _request(opener, target_url, referer=referer)
        except (HTTPError, URLError, TimeoutError, socket.timeout) as exc:
            raise ValueError(f"Halaman Tambah SPDP CMS tidak dapat dibuka: {getattr(exc, 'reason', exc)}") from exc
        if not _is_login_page(response.geturl(), content):
            _store_session(integration, jar, base_url)
            title_match = re.search(r"<title[^>]*>(.*?)</title>", content, flags=re.IGNORECASE | re.DOTALL)
            title = unescape(re.sub(r"\s+", " ", title_match.group(1)).strip()) if title_match else "Tambah SPDP"
            form_found = bool(re.search(
                r'<form[^>]+(?:id=["\']pdm-penyelesaian-pratut-form["\']|action=["\']/pidum/spdp/create["\'])',
                content,
                flags=re.IGNORECASE,
            ))
            field_names = set(re.findall(r'name=["\']([^"\']+)["\']', content, flags=re.IGNORECASE))
            return {
                "message": "Halaman Tambah SPDP CMS berhasil dibuka.",
                "http_status": getattr(response, "status", 200),
                "url": response.geturl(),
                "title": title,
                "form_found": form_found,
                "field_count": len(field_names),
                "session_reused": session_reused,
            }
        if attempt == 0:
            connect(user_id, reuse_valid=False)
            session_reused = False
            integration.refresh_from_db()

    raise ValueError("Sesi CMS belum dapat membuka halaman Tambah SPDP. Silakan periksa akun CMS.")
