from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.settings_view, name="index"),
    path("setting/", views.settings_view, name="settings"),
    path("konfigurasi-menu/", views.menu_settings_view, name="menu_settings"),
    path("template/", views.template_settings_view, name="template_settings"),
    path("aplikasi/tandai-dibaca/", views.mark_web_notifications_read, name="mark_web_notifications_read"),
    path("whatsapp/status/", views.whatsapp_status, name="whatsapp_status"),
    path("whatsapp/start/", views.whatsapp_start, name="whatsapp_start"),
    path("whatsapp/logout/", views.whatsapp_logout, name="whatsapp_logout"),
    path("whatsapp/test-message/", views.whatsapp_test_message, name="whatsapp_test_message"),
    path("telegram/fetch-chat-id/", views.telegram_fetch_chat_id, name="telegram_fetch_chat_id"),
    path("telegram/test-message/", views.telegram_test_message, name="telegram_test_message"),
]
