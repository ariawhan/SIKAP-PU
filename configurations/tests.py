from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from .models import (
    CMSIntegration,
    CMSServiceConfiguration,
    DocumentLayoutConfiguration,
    DocumentTemplateConfiguration,
    InstitutionConfiguration,
    InvestigatorInstitution,
    InvestigatorUnit,
    LetterNumberCaseType,
    LetterNumberCode,
    LetterNumberConfiguration,
    SipedeIntegration,
)
from .layouts import P16_LAYOUT_DEFAULTS, document_layout_style, validate_document_layout
from . import sipede
from .sipede import decrypt, encrypt


class ConfigurationAccessTests(TestCase):
    def setUp(self):
        admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin", "sort_order": 20})
        super_role, _ = Role.objects.get_or_create(code=Role.SUPER_ADMIN, defaults={"name": "Super Admin", "sort_order": 10})
        self.admin = User.objects.create_user("admin-config", "admin-config@test.id", "rahasia-kuat")
        self.superadmin = User.objects.create_user("super-config", "super-config@test.id", "rahasia-kuat")
        self.other_user = User.objects.create_user("user-config", "user-config@test.id", "rahasia-kuat")
        self.admin.roles.add(admin_role)
        self.superadmin.roles.add(super_role)

    def test_admin_cannot_open_configuration(self):
        self.client.force_login(self.admin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        self.assertEqual(self.client.get(reverse("configurations:institution")).status_code, 403)
        self.assertEqual(self.client.get(reverse("configurations:investigators")).status_code, 403)
        self.assertEqual(self.client.get(reverse("configurations:letter_number")).status_code, 403)
        self.assertEqual(self.client.get(reverse("configurations:letter_number_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("configurations:document_layout")).status_code, 403)
        self.assertEqual(self.client.get(reverse("configurations:document_template_settings")).status_code, 403)
        self.assertEqual(self.client.get(reverse("configurations:letter_number_detail", args=[letter_number.pk])).status_code, 403)

    def test_superadmin_can_save_and_reset_document_template_per_menu(self):
        self.client.force_login(self.superadmin)
        page = self.client.get(reverse("configurations:document_template_settings"), {"template": "p21"})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Template Generate Dokumen")
        self.assertContains(page, "SOP Form-7")
        self.assertContains(page, 'name="section__body_html"')

        response = self.client.post(reverse("configurations:document_template_settings"), {
            "template_key": "p21",
            "action": "save",
            "section__subject_html": "Perihal {{ suspect_names }}",
            "section__legal_basis_html": "<ol><li>Dasar khusus</li></ol>",
            "section__body_html": "<p>Isi khusus {{ suspect_names }}</p>",
            "section__copies_html": "<ol><li>Arsip</li></ol>",
        })
        self.assertRedirects(response, f'{reverse("configurations:document_template_settings")}?template=p21')
        configuration = DocumentTemplateConfiguration.objects.get(template_key="p21")
        self.assertEqual(configuration.updated_by, self.superadmin)
        self.assertIn("suspect_names", configuration.sections["body_html"])

        reset = self.client.post(reverse("configurations:document_template_settings"), {
            "template_key": "p21", "action": "reset",
        })
        self.assertRedirects(reset, f'{reverse("configurations:document_template_settings")}?template=p21')
        self.assertFalse(DocumentTemplateConfiguration.objects.filter(template_key="p21").exists())

    def test_invalid_document_template_syntax_is_rejected(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("configurations:document_template_settings"), {
            "template_key": "p21",
            "action": "save",
            "section__subject_html": "{% if suspect_names %}",
            "section__legal_basis_html": "",
            "section__body_html": "",
            "section__copies_html": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sintaks template tidak valid")
        self.assertFalse(DocumentTemplateConfiguration.objects.exists())

    def test_admin_can_open_integration_pages(self):
        self.client.force_login(self.admin)
        sipede_response = self.client.get(reverse("configurations:sipede_integration"))
        cms_response = self.client.get(reverse("configurations:cms_integration"))
        self.assertEqual(sipede_response.status_code, 200)
        self.assertEqual(cms_response.status_code, 200)
        self.assertContains(sipede_response, "<b>Integrasi</b>", html=True)
        self.assertContains(cms_response, "<b>Integrasi</b>", html=True)

    def test_admin_can_configure_other_users_cms_and_sipede_accounts(self):
        self.client.force_login(self.admin)

        cms_page = self.client.get(
            reverse("configurations:cms_integration"),
            {"user": self.other_user.pk},
        )
        self.assertEqual(cms_page.status_code, 200)
        self.assertContains(cms_page, f'name="target_user_id" value="{self.other_user.pk}"')
        self.assertContains(cms_page, "@user-config")

        cms_response = self.client.post(reverse("configurations:cms_integration"), {
            "target_user_id": self.other_user.pk,
            "username": "cms-user-lain",
            "password": "password-cms",
        })
        self.assertRedirects(cms_response, reverse("configurations:cms_integration"))
        self.assertEqual(CMSIntegration.objects.get(user=self.other_user).username, "cms-user-lain")
        self.assertFalse(CMSIntegration.objects.filter(user=self.admin).exists())

        sipede_response = self.client.post(reverse("configurations:sipede_integration"), {
            "target_user_id": self.other_user.pk,
            "username": "sipede-user-lain",
            "password": "password-sipede",
        })
        self.assertRedirects(sipede_response, reverse("configurations:sipede_integration"))
        self.assertEqual(SipedeIntegration.objects.get(user=self.other_user).username, "sipede-user-lain")
        self.assertFalse(SipedeIntegration.objects.filter(user=self.admin).exists())

    def test_user_can_configure_own_cms_credentials_but_not_shared_address(self):
        self.client.force_login(self.other_user)
        cms_url = reverse("configurations:cms_integration")
        cms_page = self.client.get(cms_url)
        self.assertEqual(cms_page.status_code, 200)
        self.assertNotContains(cms_page, 'name="base_url"')
        sipede_page = self.client.get(reverse("configurations:sipede_integration"))
        self.assertNotContains(sipede_page, f'href="{cms_url}"')
        self.assertEqual(self.client.post(cms_url, {
            "target_user_id": self.admin.pk,
            "username": "tidak-boleh",
            "password": "password",
        }).status_code, 403)
        self.assertEqual(self.client.post(cms_url, {
            "action": "save_cms_address",
            "base_url": "https://cms.invalid.test",
        }).status_code, 403)
        response = self.client.post(cms_url, {
            "username": "cms-pribadi",
            "password": "password",
        })
        self.assertRedirects(response, cms_url)
        self.assertEqual(CMSIntegration.objects.get(user=self.other_user).username, "cms-pribadi")
        self.assertFalse(CMSServiceConfiguration.objects.exists())
        self.assertFalse(CMSIntegration.objects.filter(user=self.admin).exists())

    def test_admin_starts_sipede_session_for_selected_user(self):
        self.client.force_login(self.admin)
        with patch("configurations.views.sipede.start", return_value="auth-user-lain") as start:
            response = self.client.post(reverse("configurations:sipede_connect_start"), {
                "target_user_id": self.other_user.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["auth_id"], "auth-user-lain")
        start.assert_called_once_with(self.other_user.pk)

    @override_settings(DEV_BROWSER_AUTO_RELOAD=True)
    def test_development_browser_reload_token_is_available(self):
        response = self.client.get(reverse("dev_browser_reload_token"))
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.json()["token"], r"^\d+$")
        self.assertEqual(response["Cache-Control"], "no-store, max-age=0")

    def test_integration_menu_hides_cms_configuration(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("configurations:sipede_integration"))
        self.assertContains(response, "<b>Integrasi</b>", html=True)
        self.assertContains(response, "Integrasi SIPede")
        self.assertNotContains(response, "Integrasi CMS")
        self.assertContains(response, "img/sipede-color.png")
        self.assertNotContains(response, "img/logo-kejaksaan-p16-clean.png")

        response = self.client.get(reverse("configurations:cms_integration"))
        self.assertContains(response, "Integrasi CMS")
        self.assertContains(response, "Daftar Akun CMS Pengguna")

    def test_sipede_connection_uses_modal_interface(self):
        self.client.force_login(self.admin)
        SipedeIntegration.objects.create(
            user=self.admin,
            username="operator-sipede",
            password_encrypted=encrypt("rahasia-sipede"),
        )
        response = self.client.get(reverse("configurations:sipede_integration"))
        self.assertContains(response, "data-sipede-modal")
        self.assertContains(response, "data-sipede-captcha-form")
        self.assertContains(response, "data-sipede-retry")
        self.assertContains(response, "sipede-integration.css")
        self.assertContains(response, "sipede-integration.js")

    def test_updating_sipede_without_password_keeps_credentials_and_session(self):
        self.client.force_login(self.admin)
        encrypted_password = encrypt("tetap-rahasia")
        integration = SipedeIntegration.objects.create(
            user=self.admin,
            username="operator-sipede",
            password_encrypted=encrypted_password,
            session_encrypted="sesi-yang-masih-aktif",
        )
        response = self.client.post(reverse("configurations:sipede_integration"), {
            "username": "operator-sipede",
            "password": "",
        })
        self.assertRedirects(response, reverse("configurations:sipede_integration"))
        integration.refresh_from_db()
        self.assertEqual(integration.password_encrypted, encrypted_password)
        self.assertEqual(integration.session_encrypted, "sesi-yang-masih-aktif")

    def test_sipede_network_error_is_presented_as_friendly_message(self):
        message = sipede._friendly_error(Exception("net::ERR_NETWORK_ACCESS_DENIED"))
        self.assertIn("Akses jaringan Chrome ke SIPede ditolak", message)
        self.assertNotIn("Page.goto", message)

    def test_sipede_cancel_only_cancels_owned_session(self):
        self.client.force_login(self.admin)
        auth_id = "test-auth-session"
        with sipede._lock:
            sipede._sessions[auth_id] = {
                "user_id": self.admin.pk,
                "status": "captcha",
                "message": "Masukkan CAPTCHA",
                "cancelled": False,
            }
        try:
            response = self.client.post(reverse("configurations:sipede_connect_cancel", args=[auth_id]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(sipede.state_for(self.admin.pk, auth_id)["status"], "cancelled")
        finally:
            with sipede._lock:
                sipede._sessions.pop(auth_id, None)

    def test_superadmin_can_save_cms_credentials_encrypted(self):
        self.client.force_login(self.superadmin)
        password = "cms-rahasia-123"
        response = self.client.post(reverse("configurations:cms_integration"), {
            "username": "operator-cms",
            "password": password,
        })
        self.assertRedirects(response, reverse("configurations:cms_integration"))
        integration = CMSIntegration.objects.get(user=self.superadmin)
        self.assertEqual(integration.username, "operator-cms")
        self.assertNotEqual(integration.password_encrypted, password)
        self.assertEqual(decrypt(integration.password_encrypted), password)
        response = self.client.post(reverse("configurations:cms_integration"), {
            "action": "save_cms_address",
            "base_url": "https://cms.example.test",
        })
        self.assertRedirects(response, reverse("configurations:cms_integration"))
        self.assertEqual(CMSServiceConfiguration.objects.get().base_url, "https://cms.example.test")
        self.client.force_login(self.other_user)
        user_page = self.client.get(reverse("configurations:cms_integration"))
        self.assertContains(user_page, "https://cms.example.test")
        self.assertNotContains(user_page, 'name="base_url"')

    def test_updating_cms_without_password_keeps_existing_password(self):
        self.client.force_login(self.superadmin)
        encrypted_password = encrypt("tetap-rahasia")
        integration = CMSIntegration.objects.create(
            user=self.superadmin,
            username="operator-lama",
            password_encrypted=encrypted_password,
        )
        response = self.client.post(reverse("configurations:cms_integration"), {
            "username": "operator-baru",
            "password": "",
        })
        self.assertRedirects(response, reverse("configurations:cms_integration"))
        integration.refresh_from_db()
        self.assertEqual(integration.password_encrypted, encrypted_password)

    def test_document_layout_page_has_visual_designer(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("configurations:document_layout"))
        self.assertContains(response, "Tata Letak Dokumen")
        self.assertContains(response, "Panel Pengaturan")
        self.assertContains(response, "data-layout-designer")
        self.assertContains(response, "data-layout-paper")
        self.assertContains(response, "data-layout-target=", count=4)
        self.assertContains(response, "data-margin-handle=", count=4)
        self.assertContains(response, "vendor/interact/interact.min.js")
        self.assertContains(response, "Simpan Tata Letak")

    def test_superadmin_can_save_p16_document_layout(self):
        self.client.force_login(self.superadmin)
        payload = {key: str(value) for key, value in P16_LAYOUT_DEFAULTS.items()}
        payload.update({"template_key": "p16", "margin_top_cm": "1.4", "signature_right_pt": "32"})
        response = self.client.post(reverse("configurations:document_layout"), payload)
        self.assertRedirects(response, reverse("configurations:document_layout"))
        configuration = DocumentLayoutConfiguration.objects.get(template_key="p16")
        self.assertEqual(configuration.settings["margin_top_cm"], 1.4)
        self.assertEqual(configuration.settings["signature_right_pt"], 32)
        self.assertEqual(configuration.updated_by, self.superadmin)

    def test_invalid_document_layout_is_not_saved(self):
        self.client.force_login(self.superadmin)
        payload = {key: str(value) for key, value in P16_LAYOUT_DEFAULTS.items()}
        payload.update({"template_key": "p16", "margin_left_cm": "99"})
        response = self.client.post(reverse("configurations:document_layout"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nilai harus antara")
        configuration = DocumentLayoutConfiguration.objects.get(template_key="p16")
        self.assertEqual(configuration.settings["margin_left_cm"], 2)

    def test_layout_validation_only_emits_safe_css_values(self):
        layout, errors = validate_document_layout("p16", {**P16_LAYOUT_DEFAULTS, "font_family": "url(evil)"})
        self.assertIn("font_family", errors)
        self.assertNotIn("url", document_layout_style("p16", layout))

    def test_superadmin_can_save_single_institution_configuration(self):
        self.client.force_login(self.superadmin)
        data = {
            "institution_name": "Kejaksaan Republik Indonesia",
            "work_unit": "Kejaksaan Negeri Contoh",
            "institution_code": "KEJARI-CONTOH",
            "address": "Jalan Keadilan Nomor 1",
            "city": "Denpasar",
            "province": "Bali",
            "postal_code": "80111",
            "phone": "0361-123456",
            "email": "pidum@kejaksaan.go.id",
            "website": "https://kejaksaan.go.id",
            "leader_name": "Nama Pimpinan",
            "leader_rank": "Jaksa Utama Pratama",
            "leader_nip": "198001012005011001",
            "leader_title": "Kepala Kejaksaan Negeri",
        }
        response = self.client.post(reverse("configurations:institution"), data)
        self.assertRedirects(response, reverse("configurations:institution"))
        self.assertEqual(InstitutionConfiguration.objects.count(), 1)
        configuration = InstitutionConfiguration.objects.get()
        self.assertEqual(configuration.updated_by, self.superadmin)
        self.assertEqual(configuration.leader_rank, "Jaksa Utama Pratama")

    def test_investigator_configuration_page_shows_nested_units(self):
        self.client.force_login(self.superadmin)
        institution = InvestigatorInstitution.objects.create(name="Kepolisian Negara Republik Indonesia")
        InvestigatorUnit.objects.create(institution=institution, name="Satreskrim Polres Buleleng")
        response = self.client.get(reverse("configurations:investigators"))
        self.assertContains(response, "Konfigurasi Instansi Penyidik")
        self.assertContains(response, "Kepolisian Negara Republik Indonesia")
        self.assertContains(response, "Satreskrim Polres Buleleng")
        self.assertContains(response, "Tambah Pelaksana")

    def test_superadmin_can_add_investigator_institution(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("configurations:investigators"), {
            "action": "add_institution",
            "name": "Kepolisian Negara Republik Indonesia",
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("configurations:investigators"))
        institution = InvestigatorInstitution.objects.get()
        self.assertEqual(institution.name, "Kepolisian Negara Republik Indonesia")
        self.assertEqual(institution.created_by, self.superadmin)

    def test_superadmin_can_add_investigator_unit_inside_institution(self):
        self.client.force_login(self.superadmin)
        institution = InvestigatorInstitution.objects.create(name="Kepolisian Negara Republik Indonesia")
        response = self.client.post(reverse("configurations:investigators"), {
            "action": "add_unit",
            "institution": institution.pk,
            "name": "Satreskrim Polres Buleleng",
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("configurations:investigators"))
        unit = InvestigatorUnit.objects.get()
        self.assertEqual(unit.institution, institution)
        self.assertEqual(unit.name, "Satreskrim Polres Buleleng")
        self.assertEqual(unit.created_by, self.superadmin)

    def test_duplicate_investigator_unit_is_rejected_in_same_institution(self):
        self.client.force_login(self.superadmin)
        institution = InvestigatorInstitution.objects.create(name="Kepolisian Negara Republik Indonesia")
        InvestigatorUnit.objects.create(institution=institution, name="Satreskrim Polres Buleleng")
        response = self.client.post(reverse("configurations:investigators"), {
            "action": "add_unit",
            "institution": institution.pk,
            "name": "satreskrim polres buleleng",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(institution.units.count(), 1)
        self.assertContains(response, "sudah terdaftar di instansi tersebut")

    def test_letter_number_preview_and_validation(self):
        config = LetterNumberConfiguration(
            format_template="{nomor}/{kode}/{bulan}/{tahun}", letter_code="B", last_number=9, number_padding=3
        )
        config.full_clean()
        self.assertRegex(config.preview(), r"010/B/[IVX]+/\d{4}")

    def test_unknown_letter_number_variable_is_rejected(self):
        config = LetterNumberConfiguration(format_template="{nomor}/{tidak_ada}")
        with self.assertRaisesMessage(Exception, "Variabel tidak dikenal"):
            config.full_clean()

    def test_letter_number_page_only_shows_directorate_code_table(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("configurations:letter_number"))
        self.assertContains(response, "Tambah Nomor Surat")
        self.assertContains(response, "Dir A")
        self.assertContains(response, "Eoh")
        self.assertContains(response, "Dir D dan E")
        self.assertContains(response, "Eku")
        self.assertContains(response, "Aksi")
        self.assertContains(response, "Edit")
        self.assertContains(response, "Hapus")
        self.assertNotContains(response, "Format Penomoran")
        self.assertNotContains(response, "Kode Masalah")

    def test_create_page_has_no_case_type_section_yet(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("configurations:letter_number_create"))
        self.assertContains(response, "Simpan &amp; Lanjutkan")
        self.assertNotContains(response, "Daftar Jenis Perkara")
        self.assertNotContains(response, "Tambah Jenis Perkara")

    def test_superadmin_can_add_letter_number_then_redirects_to_detail(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("configurations:letter_number_create"), {
            "action": "save_letter_number",
            "directorate": "Dir F",
            "code": "Esa",
        })
        letter_number = LetterNumberCode.objects.get(directorate="Dir F")
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        self.assertEqual(letter_number.code, "Esa")
        self.assertEqual(letter_number.created_by, self.superadmin)

    def test_duplicate_letter_number_is_rejected(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("configurations:letter_number_create"), {
            "action": "save_letter_number",
            "directorate": "dir a",
            "code": "Ebaru",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(LetterNumberCode.objects.count(), 4)
        self.assertContains(response, "Direktorat ini sudah terdaftar.")

    def test_duplicate_letter_number_code_is_allowed_for_different_directorate(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("configurations:letter_number_create"), {
            "action": "save_letter_number",
            "directorate": "Dir F",
            "code": "Eoh",
        })
        letter_number = LetterNumberCode.objects.get(directorate="Dir F")
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        self.assertTrue(LetterNumberCode.objects.filter(code="Eoh").count() >= 2)

    def test_superadmin_can_edit_letter_number(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        response = self.client.post(reverse("configurations:letter_number_detail", args=[letter_number.pk]), {
            "action": "save_letter_number",
            "directorate": "Dir A Utama",
            "code": "Eoh-1",
        })
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        letter_number.refresh_from_db()
        self.assertEqual(letter_number.directorate, "Dir A Utama")
        self.assertEqual(letter_number.code, "Eoh-1")

    def test_superadmin_can_delete_letter_number(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir C")
        response = self.client.post(reverse("configurations:letter_number"), {
            "action": "delete_letter_number",
            "letter_number_id": letter_number.pk,
        })
        self.assertRedirects(response, reverse("configurations:letter_number"))
        self.assertFalse(LetterNumberCode.objects.filter(pk=letter_number.pk).exists())

    def test_detail_page_shows_case_type_table_with_pagination(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        for index in range(12):
            LetterNumberCaseType.objects.create(letter_number=letter_number, name=f"Jenis {index}")
        response = self.client.get(reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        self.assertContains(response, "Daftar Jenis Perkara")
        self.assertContains(response, "12 jenis perkara")
        self.assertContains(response, "pagination-nav")
        self.assertContains(response, "Jenis 0")
        self.assertNotContains(response, "Jenis 11")

    def test_superadmin_can_add_case_type(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        response = self.client.post(reverse("configurations:letter_number_detail", args=[letter_number.pk]), {
            "action": "add_case_type",
            "name": "Narkotika",
        })
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        self.assertEqual(list(letter_number.case_types.values_list("name", flat=True)), ["Narkotika"])

    def test_duplicate_case_type_is_rejected_for_same_letter_number(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        LetterNumberCaseType.objects.create(letter_number=letter_number, name="Narkotika")
        response = self.client.post(reverse("configurations:letter_number_detail", args=[letter_number.pk]), {
            "action": "add_case_type",
            "name": "narkotika",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(letter_number.case_types.count(), 1)
        self.assertContains(response, "sudah terdaftar untuk nomor surat ini")

    def test_same_case_type_name_is_allowed_for_different_letter_number(self):
        self.client.force_login(self.superadmin)
        dir_a = LetterNumberCode.objects.get(directorate="Dir A")
        dir_b = LetterNumberCode.objects.get(directorate="Dir B")
        LetterNumberCaseType.objects.create(letter_number=dir_a, name="Narkotika")
        response = self.client.post(reverse("configurations:letter_number_detail", args=[dir_b.pk]), {
            "action": "add_case_type",
            "name": "Narkotika",
        })
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[dir_b.pk]))
        self.assertEqual(dir_b.case_types.count(), 1)

    def test_superadmin_can_edit_case_type(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        case_type = LetterNumberCaseType.objects.create(letter_number=letter_number, name="Narkotika")
        response = self.client.post(reverse("configurations:letter_number_detail", args=[letter_number.pk]), {
            "action": "edit_case_type",
            "case_type_id": case_type.pk,
            "name": "Narkotika Golongan I",
        })
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        case_type.refresh_from_db()
        self.assertEqual(case_type.name, "Narkotika Golongan I")

    def test_superadmin_can_delete_case_type(self):
        self.client.force_login(self.superadmin)
        letter_number = LetterNumberCode.objects.get(directorate="Dir A")
        case_type = LetterNumberCaseType.objects.create(letter_number=letter_number, name="Narkotika")
        response = self.client.post(reverse("configurations:letter_number_detail", args=[letter_number.pk]), {
            "action": "delete_case_type",
            "case_type_id": case_type.pk,
        })
        self.assertRedirects(response, reverse("configurations:letter_number_detail", args=[letter_number.pk]))
        self.assertFalse(LetterNumberCaseType.objects.filter(pk=case_type.pk).exists())
