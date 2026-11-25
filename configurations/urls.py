from django.urls import path
from . import views

app_name = "configurations"
urlpatterns = [
    path("instansi/", views.institution, name="institution"),
    path("integrasi/sipede/", views.sipede_integration, name="sipede_integration"),
    path("integrasi/cms/", views.cms_integration, name="cms_integration"),
    path("integrasi/cms/connect/", views.cms_connect, name="cms_connect"),
    path("integrasi/sipede/connect/", views.sipede_connect_start, name="sipede_connect_start"),
    path("integrasi/sipede/connect/<str:auth_id>/", views.sipede_connect_status, name="sipede_connect_status"),
    path("integrasi/sipede/connect/<str:auth_id>/captcha/", views.sipede_connect_captcha, name="sipede_connect_captcha"),
    path("integrasi/sipede/connect/<str:auth_id>/cancel/", views.sipede_connect_cancel, name="sipede_connect_cancel"),
    path("tata-letak-dokumen/", views.document_layout, name="document_layout"),
    path("template-dokumen/", views.document_template_settings, name="document_template_settings"),
    path("penyidik/", views.investigators, name="investigators"),
    path("nomor-surat/", views.letter_number, name="letter_number"),
    path("nomor-surat/tambah/", views.letter_number_form, name="letter_number_create"),
    path("nomor-surat/<int:pk>/", views.letter_number_form, name="letter_number_detail"),
]
