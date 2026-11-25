"""Auto-refresh helpers that are available only during local development."""

from pathlib import Path
from time import monotonic

from django.conf import settings
from django.http import Http404, JsonResponse


WATCHED_DIRECTORIES = (
    "accounts",
    "cases",
    "configurations",
    "dashboard",
    "notifications",
    "templates",
    "static",
)
WATCHED_EXTENSIONS = {".py", ".html", ".css", ".js"}
_cached_token = "0"
_cached_at = 0.0


def source_token():
    """Return the latest modification time, with a brief cache for browser polling."""
    global _cached_token, _cached_at
    now = monotonic()
    if now - _cached_at < 1:
        return _cached_token

    latest = 0
    for directory_name in WATCHED_DIRECTORIES:
        directory = Path(settings.BASE_DIR, directory_name)
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in WATCHED_EXTENSIONS:
                latest = max(latest, path.stat().st_mtime_ns)
    _cached_token = str(latest)
    _cached_at = now
    return _cached_token


def browser_reload_token(request):
    if not settings.DEV_BROWSER_AUTO_RELOAD:
        raise Http404
    response = JsonResponse({"token": source_token()})
    response["Cache-Control"] = "no-store, max-age=0"
    return response
