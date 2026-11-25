from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from .dev_reload import browser_reload_token

urlpatterns = [path("django-admin/", admin.site.urls), path("", include("accounts.urls")), path("", include("dashboard.urls")), path("konfigurasi/", include("configurations.urls")), path("perkara/", include("cases.urls")), path("notifikasi/", include("notifications.urls")), path("__dev__/reload-token/", browser_reload_token, name="dev_browser_reload_token")]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
