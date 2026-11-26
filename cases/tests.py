import json
import io
import tempfile
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from configurations.models import (
    CMSIntegration,
    DocumentTemplateConfiguration,
    InstitutionConfiguration,
    InvestigatorInstitution,
    InvestigatorUnit,
    LetterNumberCaseType,
    LetterNumberCode,
)
from notifications.models import NotificationLog, NotificationSetting, WebNotification
from notifications.services import process_notification_queue
from .forms import SPDPForm
from .models import CaseDocumentDraft, CaseInvestigator, CoordinationMinutesDraft, P16Assignment, P16Draft, P17Draft, P21Draft, Receipt, SOPForm02Draft, SOPForm03Draft, SOPForm1BDraft, SPDP, StageOne, Suspect, Victim
from .p17_content import build_p17_preview
from .reminders import case_deadline_for_spdp


class SPDPTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("petugas-spdp", "spdp@test.id", "rahasia-kuat")
        self.admin_role = Role.objects.get(code=Role.ADMIN)
        self.kasi_role = Role.objects.get(code=Role.KASI_PIDUM)
        self.prosecutor_role = Role.objects.get(code=Role.PROSECUTOR)
        self.employee_role = Role.objects.get(code=Role.EMPLOYEE)
        self.user.roles.add(self.admin_role)
        InstitutionConfiguration.objects.create(
            work_unit="Kejaksaan Negeri Buleleng",
            institution_name="Kejaksaan Republik Indonesia",
            institution_code="N.1.11",
        )
        investigator = InvestigatorInstitution.objects.create(name="Kepolisian Negara Republik Indonesia")
        InvestigatorUnit.objects.create(institution=investigator, name="Satreskrim Polres Buleleng")
        letter_number_code = LetterNumberCode.objects.create(directorate="Direktorat Umum", code="Um")
        LetterNumberCaseType.objects.create(letter_number=letter_number_code, name="Pencurian")
        self.client.force_login(self.user)
        self.data = {
            "origin": "Polres Buleleng",
            "directorate": "Direktorat Umum",
            "case_type": "Pencurian",
            "investigator_agency": "Kepolisian Negara Republik Indonesia",
            "investigating_unit": "Satreskrim Polres Buleleng",
            "investigation_order_number": "SP.Sidik/10/VIII/2026",
            "investigation_order_date": "2026-08-01",
            "letter_number": "B/100/VIII/2026/Reskrim",
            "letter_date": "2026-08-02",
            "received_date": "2026-08-03",
            "work_area": "22.02",
            "incident_at": "2026-07-30T10:30",
            "incident_place": "Kabupaten Buleleng",
            "legal_subject": "dewasa",
            "case_summary": "Dugaan tindak pidana yang sedang disidik.",
            "laws_and_articles": "Pasal 362 KUHP",
            "suspects-TOTAL_FORMS": "1",
            "suspects-INITIAL_FORMS": "0",
            "suspects-MIN_NUM_FORMS": "0",
            "suspects-MAX_NUM_FORMS": "1000",
            "suspects-0-name": "Tersangka Satu",
            "suspects-0-alias": "TS",
            "suspects-0-gender": "L",
            "suspects-0-birth_place": "Singaraja",
            "suspects-0-birth_date": "1990-01-01",
            "suspects-0-nationality": "Indonesia",
            "victims-TOTAL_FORMS": "1",
            "victims-INITIAL_FORMS": "0",
            "victims-MIN_NUM_FORMS": "0",
            "victims-MAX_NUM_FORMS": "1000",
            "victims-0-nationality": "Indonesia",
            "receipts-TOTAL_FORMS": "1",
            "receipts-INITIAL_FORMS": "0",
            "receipts-MIN_NUM_FORMS": "0",
            "receipts-MAX_NUM_FORMS": "1000",
            "investigators-TOTAL_FORMS": "1",
            "investigators-INITIAL_FORMS": "0",
            "investigators-MIN_NUM_FORMS": "0",
            "investigators-MAX_NUM_FORMS": "1000",
        }

    def test_login_is_required(self):
        self.client.logout()
        response = self.client.get(reverse("cases:spdp_create"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('cases:spdp_create')}")

    def test_spdp_form_shows_pelaku_section_and_modal(self):
        response = self.client.get(reverse("cases:spdp_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Data Pelaku")
        self.assertContains(response, "Wilayah kerja / Satuan kerja")
        self.assertContains(response, "Kejaksaan Negeri Buleleng")
        self.assertContains(response, "readonly")
        self.assertContains(response, "disabled")
        self.assertContains(response, "data-suspect-dialog")
        self.assertContains(response, "data-suspect-summary")
        self.assertContains(response, "Tambah Data Pelaku")
        self.assertContains(response, "data-cancel-suspect-dialog")
        self.assertContains(response, "data-finish-suspect-dialog")
        self.assertContains(response, "Data Korban")
        self.assertContains(response, "data-victim-dialog")
        self.assertContains(response, "data-victim-summary")
        self.assertContains(response, "Tambah Data Korban")
        self.assertContains(response, "data-cancel-victim-dialog")
        self.assertContains(response, "data-finish-victim-dialog")
        self.assertContains(response, "Tanda Terima")
        self.assertContains(response, "data-receipt-dialog")
        self.assertContains(response, "data-receipt-summary")
        self.assertContains(response, "Tambah Tanda Terima")
        self.assertContains(response, "receipts-0-received_at")
        self.assertContains(response, "receipts-0-investigator_nrp")
        self.assertContains(response, "Data Penyidik")
        self.assertContains(response, "Tambah Penyidik")
        self.assertContains(response, "data-investigator-dialog")
        self.assertContains(response, "data-investigator-summary")
        self.assertContains(response, "investigators-0-name")
        self.assertContains(response, "investigators-0-phone")
        self.assertNotContains(response, "Asal Surat")
        self.assertNotContains(response, 'name="origin"')
        self.assertNotContains(response, "Kode pidana")
        self.assertNotContains(response, 'name="criminal_code"')
        self.assertContains(response, "Direktorat")
        self.assertContains(response, 'name="directorate"')
        self.assertContains(response, "Jenis Perkara")
        self.assertContains(response, 'name="case_type"')
        self.assertContains(response, "Kepolisian Negara Republik Indonesia")
        self.assertContains(response, "Satreskrim Polres Buleleng")
        self.assertContains(response, "investigator-units-by-institution")
        self.assertNotContains(response, "data-remove-suspect")
        self.assertContains(response, 'name="suspects-0-nationality"')
        self.assertContains(response, "Malaysia")
        self.assertContains(response, "Amerika Serikat")
        content = response.content.decode()
        form_start = content.index('data-spdp-form')
        dialog_start = content.index('data-suspect-dialog')
        form_end = content.index('</form>', form_start)
        self.assertLess(form_start, dialog_start)
        self.assertLess(dialog_start, form_end)

    def test_create_spdp_with_multiple_pelaku(self):
        payload = {**self.data, "suspects-TOTAL_FORMS": "2"}
        payload.update({
            "suspects-1-name": "Pelaku Dua",
            "suspects-1-gender": "P",
            "suspects-1-nationality": "Indonesia",
        })
        response = self.client.post(reverse("cases:spdp_create"), payload)
        self.assertEqual(response.status_code, 302)
        spdp = SPDP.objects.get()
        self.assertEqual(list(spdp.suspects.order_by("sequence").values_list("name", flat=True)), ["Tersangka Satu", "Pelaku Dua"])

    def test_create_spdp_without_pelaku_is_allowed(self):
        payload = self.data.copy()
        for key in list(payload):
            if key.startswith("suspects-0-"):
                payload.pop(key)
        payload["suspects-0-nationality"] = "Indonesia"
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        self.assertEqual(spdp.suspects.count(), 0)

    def test_create_spdp_with_suspect(self):
        response = self.client.post(reverse("cases:spdp_create"), self.data)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        self.assertEqual(spdp.created_by, self.user)
        self.assertEqual(spdp.work_area, "Kejaksaan Negeri Buleleng")
        self.assertEqual(spdp.investigator_agency, "Kepolisian Negara Republik Indonesia")
        self.assertEqual(spdp.investigating_unit, "Satreskrim Polres Buleleng")
        self.assertEqual(spdp.suspects.get().name, "Tersangka Satu")
        self.assertEqual(spdp.victims.count(), 0)
        self.assertEqual(spdp.receipts.count(), 0)

    def test_admin_can_open_and_update_existing_case(self):
        self.client.post(reverse("cases:spdp_create"), self.data)
        spdp = SPDP.objects.get()
        suspect = spdp.suspects.get()

        page = self.client.get(reverse("cases:spdp_edit", args=[spdp.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Edit Data Perkara")

        payload = self.data.copy()
        payload.update({
            "case_summary": "Uraian perkara yang sudah diperbarui.",
            "suspects-INITIAL_FORMS": "1",
            "suspects-0-id": str(suspect.pk),
        })
        response = self.client.post(reverse("cases:spdp_edit", args=[spdp.pk]), payload)
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        spdp.refresh_from_db()
        self.assertEqual(spdp.case_summary, "Uraian perkara yang sudah diperbarui.")
        self.assertEqual(spdp.suspects.get().name, "Tersangka Satu")

    def test_investigating_unit_must_match_selected_investigator_agency(self):
        other = InvestigatorInstitution.objects.create(name="PPNS")
        InvestigatorUnit.objects.create(institution=other, name="Unit PPNS Buleleng")
        payload = {**self.data, "investigating_unit": "Unit PPNS Buleleng"}
        response = self.client.post(reverse("cases:spdp_create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SPDP.objects.count(), 0)
        self.assertContains(response, "tidak sesuai dengan instansi penyidik")

    def test_create_spdp_with_victim(self):
        payload = {
            **self.data,
            "victims-0-name": "Korban Satu",
            "victims-0-alias": "KS",
            "victims-0-gender": Victim.Gender.FEMALE,
            "victims-0-birth_place": "Denpasar",
            "victims-0-birth_date": "1995-05-05",
            "victims-0-identity_type": "KTP",
            "victims-0-identity_number": "5171010505950001",
            "victims-0-relationship": "Bukan Keluarga",
            "victims-0-occupation": "Karyawan Swasta",
            "victims-0-disability_types": ["Bukan Penyandang Disabilitas"],
        }
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        victim = spdp.victims.get()
        self.assertEqual(victim.name, "Korban Satu")
        self.assertEqual(victim.relationship, "Bukan Keluarga")
        self.assertEqual(victim.disability_types, "Bukan Penyandang Disabilitas")

    def test_create_spdp_saves_receipt_data(self):
        payload = {
            **self.data,
            "receipts-0-receipt_type": Receipt.ReceiptType.ADDITIONAL_INVESTIGATION_RESULT,
            "receipts-0-cover_letter_number": "B/TT/10/IX/2026",
            "receipts-0-cover_letter_date": "2026-09-14",
            "receipts-0-received_at": "2026-09-15T10:30",
            "receipts-0-issued_date": "2026-09-15",
            "receipts-0-recipient_name": "I Made Penerima",
            "receipts-0-recipient_rank": "Jaksa Muda",
            "receipts-0-recipient_position": "Petugas Penerima",
            "receipts-0-investigator_name": "Ipda Penyidik",
            "receipts-0-investigator_nrp": "88001122",
            "receipts-0-investigator_rank": "IPDA",
            "receipts-0-investigator_position": "Penyidik Pembantu",
        }
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        receipt = spdp.receipts.get()
        self.assertEqual(receipt.receipt_type, Receipt.ReceiptType.ADDITIONAL_INVESTIGATION_RESULT)
        self.assertEqual(receipt.recipient_name, "I Made Penerima")
        self.assertEqual(receipt.investigator_nrp, "88001122")

    def test_create_and_edit_spdp_with_multiple_investigators(self):
        payload = {
            **self.data,
            "investigators-TOTAL_FORMS": "2",
            "investigators-0-name": "IPDA I Made Penyidik",
            "investigators-0-phone": "0812-3456-7890",
            "investigators-1-name": "AIPDA Komang Penyidik",
            "investigators-1-phone": "0813 4567 8901",
        }
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        self.assertEqual(
            list(spdp.investigators.values_list("name", "phone")),
            [
                ("IPDA I Made Penyidik", "0812-3456-7890"),
                ("AIPDA Komang Penyidik", "0813 4567 8901"),
            ],
        )

        first, second = list(spdp.investigators.all())
        suspect = spdp.suspects.get()
        edit_payload = {
            **self.data,
            "suspects-INITIAL_FORMS": "1",
            "suspects-0-id": str(suspect.pk),
            "investigators-TOTAL_FORMS": "2",
            "investigators-INITIAL_FORMS": "2",
            "investigators-0-id": str(first.pk),
            "investigators-0-name": "IPDA I Made Diperbarui",
            "investigators-0-phone": "081299999999",
            "investigators-1-id": str(second.pk),
            "investigators-1-name": second.name,
            "investigators-1-phone": second.phone,
            "investigators-1-DELETE": "on",
        }
        response = self.client.post(reverse("cases:spdp_edit", args=[spdp.pk]), edit_payload)
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        self.assertEqual(spdp.investigators.count(), 1)
        self.assertEqual(spdp.investigators.get().name, "IPDA I Made Diperbarui")
        self.assertEqual(spdp.investigators.get().phone, "081299999999")

    def test_investigator_phone_is_validated(self):
        payload = {
            **self.data,
            "investigators-0-name": "Penyidik Uji",
            "investigators-0-phone": "nomor salah",
        }
        response = self.client.post(reverse("cases:spdp_create"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CaseInvestigator.objects.exists())
        self.assertContains(response, "Nomor HP penyidik tidak valid")

    def test_receipt_recipient_dropdown_uses_prosecutor_profile(self):
        prosecutor = User.objects.create_user(
            "jaksa-penerima",
            "jaksa-penerima@test.id",
            "rahasia-kuat",
            first_name="I Made",
            last_name="Jaksa",
            rank="Jaksa Madya",
            nip="198001012005011001",
        )
        prosecutor.roles.add(self.prosecutor_role)

        page = self.client.get(reverse("cases:spdp_create"))
        self.assertContains(page, "--- Pilih Jaksa Penerima ---")
        self.assertContains(page, "I Made Jaksa")
        self.assertContains(page, 'id="receipt-prosecutor-profiles"')

        payload = {
            **self.data,
            "receipts-0-receipt_type": Receipt.ReceiptType.INVESTIGATION_RESULT,
            "receipts-0-received_at": "2026-09-15T10:30",
            "receipts-0-recipient_user": str(prosecutor.pk),
            "receipts-0-recipient_name": "Nama yang dimanipulasi",
            "receipts-0-recipient_rank": "Pangkat yang dimanipulasi",
            "receipts-0-recipient_position": "Jabatan yang dimanipulasi",
            "receipts-0-recipient_nip": "000",
        }
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        receipt = spdp.receipts.get()
        self.assertEqual(receipt.recipient_user, prosecutor)
        self.assertEqual(receipt.recipient_name, "I Made Jaksa")
        self.assertEqual(receipt.recipient_rank, "Jaksa Madya")
        self.assertEqual(receipt.recipient_position, "Jaksa Penuntut Umum")
        self.assertEqual(receipt.recipient_nip, "198001012005011001")

    def test_create_spdp_saves_non_indonesian_nationality(self):
        payload = {**self.data, "suspects-0-nationality": "Malaysia"}
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        self.assertEqual(spdp.suspects.get().nationality, "Malaysia")

    def test_create_spdp_saves_extended_suspect_fields(self):
        payload = {
            **self.data,
            "suspects-0-decree_number": "TAP/01/IX/2026",
            "suspects-0-decree_date": "2026-09-15",
            "suspects-0-suspect_type": Suspect.SuspectType.CORPORATE_BOARD,
            "suspects-0-corporate_position": "Direktur",
            "suspects-0-age": "36",
            "suspects-0-ethnicity": "Bali",
            "suspects-0-marital_status": "Kawin",
            "suspects-0-identity_type": "KTP",
            "suspects-0-identity_number": "5108010101900001",
            "suspects-0-phone": "081234567890",
            "suspects-0-religion": "Hindu",
            "suspects-0-education": "Diploma IV / Strata 1",
            "suspects-0-occupation": "Lainnya",
            "suspects-0-occupation_other": "Pengusaha",
            "suspects-0-disability_types": ["Bukan Penyandang Disabilitas"],
            "suspects-0-corporation_deed_number": "AHU-001",
            "suspects-0-corporation_crime_deed_date": "2026-09-01",
        }
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        suspect = spdp.suspects.get()
        self.assertEqual(suspect.decree_number, "TAP/01/IX/2026")
        self.assertEqual(suspect.suspect_type, Suspect.SuspectType.CORPORATE_BOARD)
        self.assertEqual(suspect.corporate_position, "Direktur")
        self.assertEqual(suspect.disability_types, "Bukan Penyandang Disabilitas")
        self.assertEqual(suspect.corporation_deed_number, "AHU-001")

    def test_suspect_age_is_calculated_from_birth_date(self):
        payload = {**self.data, "suspects-0-age": "99"}
        response = self.client.post(reverse("cases:spdp_create"), payload)
        spdp = SPDP.objects.get()
        self.assertRedirects(response, reverse("cases:spdp_detail", args=[spdp.pk]))
        suspect = spdp.suspects.get()
        expected_age = Suspect.calculate_age(date(1990, 1, 1), timezone.localdate())
        self.assertEqual(suspect.age, expected_age)
        self.assertNotEqual(suspect.age, 99)

    def test_duplicate_letter_number_is_rejected(self):
        SPDP.objects.create(
            origin="Polres", investigator_agency="Polri", investigating_unit="Reskrim",
            investigation_order_number="SPRIN-1", investigation_order_date=date(2026, 8, 1),
            letter_number=self.data["letter_number"], letter_date=date(2026, 8, 2),
            received_date=date(2026, 8, 3), case_summary="Uraian", laws_and_articles="Pasal",
            created_by=self.user,
        )
        response = self.client.post(reverse("cases:spdp_create"), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SPDP.objects.count(), 1)
        self.assertContains(response, "SPDP dengan Nomor SPDP telah ada")

    def test_invalid_date_order_is_rejected(self):
        invalid = {**self.data, "investigation_order_date": "2026-08-05"}
        response = self.client.post(reverse("cases:spdp_create"), invalid)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tanggal Sprindik tidak boleh setelah tanggal SPDP")

    def test_non_pdf_document_is_rejected(self):
        upload = SimpleUploadedFile("spdp.txt", b"bukan pdf", content_type="text/plain")
        form = SPDPForm(data=self.data, files={"document": upload})
        self.assertFalse(form.is_valid())
        self.assertIn("Dokumen SPDP harus berupa berkas PDF", str(form.errors))

    def create_spdp(self):
        payload = self.data.copy()
        response = self.client.post(reverse("cases:spdp_create"), payload)
        self.assertEqual(response.status_code, 302)
        return SPDP.objects.get(letter_number=self.data["letter_number"])

    def create_issued_p16_case(self, suffix):
        spdp = self.create_spdp()
        kasi = User.objects.create_user(
            f"kasi-flow-{suffix}", f"kasi-flow-{suffix}@test.id", "rahasia-kuat",
        )
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        draft.draft_number = f"PRINT-{suffix}/N.1.11/Um.1/11/2026"
        draft.save(update_fields=("draft_number", "updated_at"))
        return spdp, draft

    def create_stage_one_record(self, spdp, suffix):
        return StageOne.objects.create(
            spdp=spdp,
            case_file_number=f"BP/{suffix}/2026",
            cover_letter_number=f"B/{suffix}/2026",
            laws_and_articles=spdp.laws_and_articles,
            cover_letter_document=SimpleUploadedFile(
                f"pengantar-{suffix}.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf",
            ),
            created_by=self.user,
        )

    def p16_payload(self, draft, **overrides):
        sequence_number = (
            draft.draft_number.split("/", 1)[0].removeprefix("PRINT-")
            if draft.draft_number.startswith("PRINT-")
            else str(draft.assignment_id)
        )
        payload = {
            "draft_number": sequence_number,
            "letter_date": draft.letter_date.isoformat(),
            "consideration_html": draft.consideration_html,
            "legal_basis_html": draft.legal_basis_html,
            "offense_summary_html": draft.offense_summary_html,
            "recipient_html": draft.recipient_html,
            "instruction_html": draft.instruction_html,
            "copies_html": draft.copies_html,
            "administration_legal_basis_html": draft.administration_legal_basis_html,
            "administration_consideration_html": draft.administration_consideration_html,
            "administration_instruction_html": draft.administration_instruction_html,
            "administration_copies_html": draft.administration_copies_html,
            "prosecutors": [str(pk) for pk in draft.assignment.prosecutors.values_list("pk", flat=True)],
            "administrative_staff": [str(pk) for pk in draft.assignment.administrative_staff.values_list("pk", flat=True)],
        }
        payload.update(overrides)
        return payload

    def p17_payload(self, draft, **overrides):
        payload = {
            "letter_number": "1",
            "letter_date": draft.letter_date.isoformat(),
            "letter_nature": draft.letter_nature,
            "attachment": draft.attachment,
            "subject_html": draft.subject_html,
            "recipient_html": draft.recipient_html,
            "recipients_json": json.dumps([
                {"recipient": f"Kepala {draft.spdp.investigating_unit}", "place": "Singaraja"},
            ]),
            "body_html": draft.body_html,
            "copies_html": draft.copies_html,
        }
        payload.update(overrides)
        return payload

    def p21_payload(self, draft, **overrides):
        payload = {
            "letter_number": draft.letter_number,
            "letter_date": draft.letter_date.isoformat(),
            "letter_nature": draft.letter_nature,
            "attachment": draft.attachment,
            "subject_html": draft.subject_html,
            "legal_basis_html": draft.legal_basis_html,
            "body_html": draft.body_html,
            "copies_html": draft.copies_html,
        }
        payload.update(overrides)
        return payload

    def sop_payload(self, draft, **overrides):
        payload = {
            "letter_number": draft.letter_number,
            "letter_date": draft.letter_date.isoformat(),
            "letter_nature": draft.letter_nature,
            "attachment": draft.attachment,
            "subject_html": draft.subject_html,
            "body_html": draft.body_html,
            "copies_html": draft.copies_html,
        }
        payload.update(overrides)
        return payload

    def case_document_payload(self, draft, **overrides):
        payload = {
            "letter_number": draft.letter_number, "letter_date": draft.letter_date.isoformat(),
            "letter_nature": draft.letter_nature, "attachment": draft.attachment,
            "subject_html": draft.subject_html, "legal_basis_html": draft.legal_basis_html,
            "body_html": draft.body_html, "copies_html": draft.copies_html,
        }
        payload.update(overrides)
        return payload

    def coordination_payload(self, draft, **overrides):
        payload = {
            "meeting_date": draft.meeting_date.isoformat(),
            "meeting_place": draft.meeting_place,
            "prosecutor_name": draft.prosecutor_name,
            "prosecutor_rank": draft.prosecutor_rank,
            "prosecutor_nip": draft.prosecutor_nip,
            "investigator_name": draft.investigator_name,
            "investigator_rank": draft.investigator_rank,
            "investigator_nrp": draft.investigator_nrp,
            "investigator_position": draft.investigator_position,
            "investigator_supervisor_title": draft.investigator_supervisor_title,
            "investigator_supervisor_name": draft.investigator_supervisor_name,
            "investigator_supervisor_rank": draft.investigator_supervisor_rank,
            "investigator_supervisor_nrp": draft.investigator_supervisor_nrp,
            "prosecutor_supervisor_title": draft.prosecutor_supervisor_title,
            "prosecutor_supervisor_name": draft.prosecutor_supervisor_name,
            "prosecutor_supervisor_rank": draft.prosecutor_supervisor_rank,
            "prosecutor_supervisor_nip": draft.prosecutor_supervisor_nip,
            "body_html": draft.body_html,
        }
        payload.update(overrides)
        return payload

    def create_coordination_prerequisites(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user(
            "kasi-koordinasi", "kasi-koordinasi@test.id", "rahasia-kuat",
            first_name="I Made", last_name="Kasi", nip="198001012005011001", rank="Jaksa Madya",
        )
        prosecutor = User.objects.create_user(
            "jaksa-koordinasi", "jaksa-koordinasi@test.id", "rahasia-kuat",
            first_name="Ni Luh", last_name="Jaksa", nip="199001012015022001", rank="Jaksa Muda",
        )
        kasi.roles.add(self.kasi_role, self.prosecutor_role)
        prosecutor.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(prosecutor)
        p16, _ = P16Draft.create_for_assignment(assignment, kasi)
        return spdp, kasi, prosecutor, p16

    def test_process_p16_selects_kasi_and_changes_status(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-pidum", "kasi@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role, self.prosecutor_role)
        response = self.client.post(reverse("cases:start_p16", args=[spdp.pk]), {"kasi_pidum": kasi.pk})
        self.assertRedirects(response, reverse("cases:spdp_list"))
        spdp.refresh_from_db()
        self.assertEqual(spdp.status, SPDP.Status.PROCESS)
        self.assertEqual(spdp.p16_assignment.kasi_pidum, kasi)
        self.assertEqual(spdp.p16_assignment.status, P16Assignment.Status.WAITING_PROSECUTOR)

    def test_terminal_documents_stop_case_and_p20_waits_for_sipede_upload(self):
        spdp = self.create_spdp()
        terminal_document_creators = (
            ("SOP Form 3", lambda: SOPForm03Draft.create_for_spdp(spdp, self.user)),
            ("P-20", lambda: CaseDocumentDraft.create_for_spdp(
                spdp, CaseDocumentDraft.DocumentType.P20, self.user,
            )),
            ("SOP Form 7", lambda: CaseDocumentDraft.create_for_spdp(
                spdp, CaseDocumentDraft.DocumentType.SOP_FORM_07, self.user,
            )),
        )

        for index, (label, create_document) in enumerate(terminal_document_creators, start=1):
            with self.subTest(document=label):
                draft = create_document()
                list_page = self.client.get(reverse("cases:spdp_list"))
                self.assertEqual(
                    list_page.context["spdp_list"][0].workflow_status["label"],
                    f"Proses {label}",
                )

                draft.letter_number = f"B-{index}/N.1.11/Um.1/11/2026"
                draft.save(update_fields=("letter_number", "updated_at"))
                list_page = self.client.get(reverse("cases:spdp_list"))
                if label == "P-20":
                    workflow_status = list_page.context["spdp_list"][0].workflow_status
                    self.assertEqual(workflow_status["label"], "Proses P-20")
                    self.assertEqual(workflow_status["badge_class"], "amber")
                    draft.sipede_status = CaseDocumentDraft.SipedeStatus.UPLOADED
                    draft.save(update_fields=("sipede_status", "updated_at"))
                    list_page = self.client.get(reverse("cases:spdp_list"))
                workflow_status = list_page.context["spdp_list"][0].workflow_status
                self.assertEqual(workflow_status["label"], "Diberhentikan")
                self.assertEqual(workflow_status["badge_class"], "red")
                self.assertContains(list_page, 'class="badge red">Diberhentikan</span>')
                if label == "SOP Form 7":
                    self.assertContains(
                        self.client.get(reverse("cases:sop_form_07_list")),
                        'class="badge red">Diberhentikan</span>',
                    )

                draft.delete()

    def test_process_p16_notifies_selected_kasi_on_all_channels(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user(
            "kasi-notified",
            "kasi-notified@test.id",
            "rahasia-kuat",
            first_name="Made",
            last_name="Wijaya",
            whatsapp_number="0812-3456-7890",
            telegram_chat_id="99887766",
        )
        kasi.roles.add(self.kasi_role, self.prosecutor_role)
        NotificationSetting.objects.update_or_create(
            pk=1,
            defaults={
                "whatsapp_enabled": True,
                "telegram_enabled": True,
                "telegram_bot_token": "123456:secret-token",
            },
        )
        whatsapp_result = ({"ok": True, "result": {"key": {"id": "wa-message-1"}}}, 200)
        telegram_result = ({"ok": True, "message_id": 7788}, 200)

        with patch("notifications.services.send_whatsapp_message", return_value=whatsapp_result) as whatsapp_send:
            with patch("notifications.services.send_telegram_message", return_value=telegram_result) as telegram_send:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(
                        reverse("cases:start_p16", args=[spdp.pk]),
                        {"kasi_pidum": kasi.pk},
                    )

        self.assertRedirects(response, reverse("cases:spdp_list"))
        web_notification = WebNotification.objects.get(recipient=kasi)
        self.assertEqual(web_notification.title, "Tugas Penunjukan Jaksa P-16")
        self.assertIn(spdp.letter_number, web_notification.message)
        self.assertFalse(web_notification.is_read)
        whatsapp_send.assert_not_called()
        telegram_send.assert_not_called()
        self.assertEqual(NotificationLog.objects.filter(status=NotificationLog.Status.QUEUED).count(), 2)
        with patch("notifications.services.send_whatsapp_message", return_value=whatsapp_result) as queued_whatsapp_send:
            with patch("notifications.services.send_telegram_message", return_value=telegram_result) as queued_telegram_send:
                self.assertEqual(process_notification_queue(timezone.now() + timedelta(seconds=1)), 2)
        queued_whatsapp_send.assert_called_once()
        self.assertEqual(queued_whatsapp_send.call_args.args[0], "6281234567890")
        self.assertIn("TUGAS PENUNJUKAN JAKSA P-16", queued_whatsapp_send.call_args.args[1])
        self.assertIn("Tunjuk Jaksa", queued_whatsapp_send.call_args.args[1])
        queued_telegram_send.assert_called_once()
        self.assertEqual(queued_telegram_send.call_args.args[1], "99887766")
        self.assertEqual(NotificationLog.objects.filter(status=NotificationLog.Status.SENT).count(), 2)
        self.assertTrue(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.WHATSAPP,
            recipient="6281234567890",
            provider_message_id="wa-message-1",
        ).exists())
        self.assertTrue(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.TELEGRAM,
            recipient="99887766",
            provider_message_id="7788",
        ).exists())

    def test_selected_kasi_can_assign_multiple_prosecutors(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-pidum", "kasi@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role, self.prosecutor_role)
        first = User.objects.create_user(
            "jaksa-satu", "j1@test.id", "rahasia-kuat", rank="Jaksa Muda", nip="198001012005011001",
        )
        second = User.objects.create_user(
            "jaksa-dua", "j2@test.id", "rahasia-kuat", rank="Ajun Jaksa", nrp="61234567",
        )
        staff_one = User.objects.create_user("pegawai-satu", "p1@test.id", "rahasia-kuat")
        staff_two = User.objects.create_user("pegawai-dua", "p2@test.id", "rahasia-kuat")
        first.roles.add(self.prosecutor_role)
        second.roles.add(self.prosecutor_role)
        staff_one.roles.add(self.employee_role)
        staff_two.roles.add(self.employee_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user)
        self.client.force_login(kasi)
        response = self.client.post(reverse("cases:assign_prosecutors", args=[spdp.pk]), {
            "prosecutors": [first.pk, second.pk],
            "administrative_staff_enabled": "on",
            "administrative_staff": [staff_one.pk, staff_two.pk],
        })
        draft = P16Draft.objects.get(assignment=assignment)
        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, P16Assignment.Status.ASSIGNED)
        self.assertEqual(set(assignment.prosecutors.values_list("pk", flat=True)), {first.pk, second.pk})
        self.assertEqual(set(assignment.appointed_prosecutors.values_list("pk", flat=True)), {first.pk, second.pk})
        self.assertEqual(set(assignment.administrative_staff.values_list("pk", flat=True)), {staff_one.pk, staff_two.pk})
        self.assertEqual(draft.status, P16Draft.Status.DRAFT)
        self.assertEqual(draft.generated_by, kasi)
        self.assertEqual(draft.letter_date, timezone.localdate())
        self.assertIn("<ol>", draft.consideration_html)
        self.assertIn("<ol>", draft.legal_basis_html)
        self.assertIn("<ol>", draft.instruction_html)
        self.assertIn("<ol>", draft.administration_legal_basis_html)
        self.assertIn("<ol>", draft.administration_consideration_html)
        self.assertIn("<ol>", draft.administration_instruction_html)
        self.assertIn('data-p16-page="2"', draft.content_html)
        self.assertIn('data-p16-page="3"', draft.content_html)
        self.assertIn('data-p16-group="naskah"', draft.content_html)
        self.assertIn('data-p16-group="lampiran"', draft.content_html)
        self.assertIn('data-p16-group="administrasi"', draft.content_html)
        self.assertIn("PENUNJUKAN PETUGAS ADMINISTRASI", draft.content_html)
        self.assertIn(staff_one.display_name.upper(), draft.content_html)
        self.assertIn(staff_two.display_name.upper(), draft.content_html)
        self.assertIn("Jaksa Muda", draft.content_html)
        self.assertIn("NIP. 198001012005011001", draft.content_html)
        self.assertIn("Ajun Jaksa", draft.content_html)
        self.assertIn("NRP. 61234567", draft.content_html)
        self.assertNotIn(first.email, draft.content_html)
        self.assertNotIn(second.email, draft.content_html)
        self.assertNotIn("p16-instruction-continuation", draft.content_html)
        self.assertIn("Melaksanakan Surat Perintah ini dengan sebaik-baiknya", draft.content_html)
        self.assertIn("TIM PENUNTUT UMUM", draft.content_html)

    def test_unselected_user_cannot_assign_prosecutors(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-pidum", "kasi@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user)
        response = self.client.post(reverse("cases:assign_prosecutors", args=[spdp.pk]), {"prosecutors": []})
        self.assertEqual(response.status_code, 403)

    def test_p16_menu_list_shows_generated_draft(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-menu", "kasi-menu@test.id", "rahasia-kuat")
        jaksa = User.objects.create_user("jaksa-menu", "jaksa-menu@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        jaksa.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        assignment.prosecutors.add(jaksa)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        response = self.client.get(reverse("cases:p16_list"))
        self.assertContains(response, "Pra Penuntutan")
        self.assertContains(response, draft.draft_number)
        self.assertContains(response, "P-16")

    def test_p16_generation_uses_configured_subject_template(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p16-template", "kasi-p16-template@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        DocumentTemplateConfiguration.objects.create(
            template_key="p16",
            sections={"subject": "Perintah khusus untuk SPDP {{ spdp.letter_number }}"},
            updated_by=self.user,
        )

        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        self.assertEqual(draft.subject, f"Perintah khusus untuk SPDP {spdp.letter_number}")

    def test_stage_one_updates_case_suspect_and_closes_reminders(self):
        spdp = self.create_spdp()
        suspect = spdp.suspects.get()
        kasi = User.objects.create_user("kasi-stage-one", "kasi-stage-one@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        draft.draft_number = "PRINT-100/N.1.11/Um.1/11/2026"
        draft.save(update_fields=("draft_number", "updated_at"))
        WebNotification.objects.create(
            recipient=kasi,
            kind=WebNotification.Kind.CASE_DEADLINE,
            title="Reminder P-16",
            message="Hari ke-28",
            spdp=spdp,
        )
        payload = {
            "case_file_number": "BP/100/XI/2026/Reskrim",
            "cover_letter_number": "B/200/XI/2026/Reskrim",
            "laws_and_articles": "Pasal 362 KUHP dan Pasal 55 KUHP",
            "cover_letter_document": SimpleUploadedFile("surat-pengantar.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
            "suspects-TOTAL_FORMS": "1",
            "suspects-INITIAL_FORMS": "1",
            "suspects-MIN_NUM_FORMS": "0",
            "suspects-MAX_NUM_FORMS": "1000",
            "suspects-0-id": str(suspect.pk),
            "suspects-0-name": "Tersangka Tahap Satu",
            "suspects-0-suspect_type": "TERLAPOR",
            "suspects-0-nationality": "Indonesia",
        }
        response = self.client.post(reverse("cases:stage_one_detail", args=[spdp.pk]), payload)
        self.assertRedirects(response, reverse("cases:stage_one_detail", args=[spdp.pk]))
        stage_one = StageOne.objects.get(spdp=spdp)
        self.assertEqual(stage_one.case_file_number, "BP/100/XI/2026/Reskrim")
        spdp.refresh_from_db()
        suspect.refresh_from_db()
        self.assertEqual(spdp.laws_and_articles, "Pasal 362 KUHP dan Pasal 55 KUHP")
        self.assertEqual(suspect.name, "Tersangka Tahap Satu")
        self.assertEqual(suspect.suspect_type, "TERLAPOR")
        self.assertFalse(WebNotification.objects.filter(spdp=spdp, kind=WebNotification.Kind.CASE_DEADLINE).exists())

    def test_kasubsi_prapenuntutan_can_open_stage_one(self):
        spdp = self.create_spdp()
        kasubsi_role = Role.objects.get(code=Role.KASUBSI_PREPROSECUTION)
        kasubsi = User.objects.create_user("kasubsi-pra", "kasubsi-pra@test.id", "rahasia-kuat")
        kasubsi.roles.add(kasubsi_role)
        self.client.force_login(kasubsi)
        response = self.client.get(reverse("cases:stage_one_detail", args=[spdp.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Input Berkas Perkara")

    def test_stage_one_list_only_shows_created_records_and_uses_spdp_search(self):
        spdp = self.create_spdp()

        response = self.client.get(reverse("cases:stage_one_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tambah Tahap 1")
        self.assertEqual(len(response.context["cases"]), 0)

        response = self.client.get(reverse("cases:stage_one_select"), {"q": "B/100"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, spdp.letter_number)
        self.assertContains(response, "Dapat Diproses")
        self.assertContains(response, "Pilih SPDP")

        StageOne.objects.create(
            spdp=spdp,
            case_file_number="BP/100/XI/2026",
            cover_letter_number="B/200/XI/2026",
            laws_and_articles="Pasal 362 KUHP",
            cover_letter_document=SimpleUploadedFile(
                "pengantar.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf",
            ),
            created_by=self.user,
        )
        response = self.client.get(reverse("cases:stage_one_list"))
        self.assertContains(response, spdp.letter_number)
        self.assertContains(response, "BP/100/XI/2026")

    def test_issued_sop_form_03_blocks_stage_one(self):
        spdp = self.create_spdp()
        sop03 = SOPForm03Draft.create_for_spdp(spdp, self.user)
        sop03.letter_number = "B-300/N.1.11/Um.1/11/2026"
        sop03.save(update_fields=("letter_number", "updated_at"))

        response = self.client.get(reverse("cases:stage_one_detail", args=[spdp.pk]))
        self.assertRedirects(response, reverse("cases:stage_one_select"))
        self.assertFalse(StageOne.objects.filter(spdp=spdp).exists())

        response = self.client.get(reverse("cases:stage_one_select"), {"q": "B/100"})
        self.assertContains(response, "SOP Form 3 Terbit")
        self.assertContains(response, "Tidak dapat diproses")

    def test_all_outgoing_letter_editors_have_plt_plh_configuration(self):
        spdp = self.create_spdp()
        drafts = [
            (P17Draft.create_for_spdp(spdp, self.user), "cases:p17_draft_detail"),
            (P21Draft.create_for_spdp(spdp, self.user), "cases:p21_draft_detail"),
            (SOPForm02Draft.create_for_spdp(spdp, self.user), "cases:sop_form_02_detail"),
            (SOPForm03Draft.create_for_spdp(spdp, self.user), "cases:sop_form_03_detail"),
        ]
        for document_type, url_name in (
            (CaseDocumentDraft.DocumentType.P18, "cases:p18_detail"),
            (CaseDocumentDraft.DocumentType.P19, "cases:p19_detail"),
            (CaseDocumentDraft.DocumentType.P20, "cases:p20_detail"),
            (CaseDocumentDraft.DocumentType.SOP_FORM_07, "cases:sop_form_07_detail"),
        ):
            drafts.append((
                CaseDocumentDraft.create_for_spdp(spdp, document_type, self.user),
                url_name,
            ))

        for draft, url_name in drafts:
            with self.subTest(document=url_name):
                response = self.client.get(reverse(url_name, args=[draft.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Status Penandatangan")
                self.assertContains(response, "Pelaksana Tugas")
                self.assertContains(response, "Pelaksana Harian")

    def test_p17_saves_plt_identity_and_uses_it_in_preview(self):
        spdp = self.create_spdp()
        draft = P17Draft.create_for_spdp(spdp, self.user)
        payload = self.p17_payload(draft, **{
            "acting_type": "plt",
            "acting_name": "I Made Pejabat, S.H.",
            "acting_position": "Jaksa Madya",
            "acting_nip": "197001011999031001",
        })
        response = self.client.post(
            reverse("cases:p17_draft_detail", args=[draft.pk]), payload,
        )
        self.assertRedirects(
            response, reverse("cases:p17_draft_detail", args=[draft.pk]),
        )
        draft.refresh_from_db()
        self.assertEqual(draft.acting_type, "plt")
        self.assertEqual(draft.acting_name, "I Made Pejabat, S.H.")
        preview = build_p17_preview(draft)
        self.assertIn("Plt.", preview)
        self.assertIn("I Made Pejabat, S.H.", preview)
        self.assertIn("197001011999031001", preview)

    def test_p16_cms_picker_includes_configured_unassigned_prosecutor(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-cms", "kasi-cms@test.id", "rahasia-kuat")
        assigned = User.objects.create_user("jaksa-assigned", "jaksa-assigned@test.id", "rahasia-kuat")
        configured = User.objects.create_user("jaksa-cms", "jaksa-cms@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assigned.roles.add(self.prosecutor_role)
        configured.roles.add(self.prosecutor_role)
        CMSIntegration.objects.create(
            user=configured,
            username="akun-cms-jaksa",
            password_encrypted="terenkripsi",
        )
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(assigned)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)

        response = self.client.get(reverse("cases:p16_draft_detail", args=[draft.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "akun-cms-jaksa")
        self.assertContains(response, f'value="{configured.pk}" checked')
        self.assertNotContains(response, "Belum ada akun CMS yang tersedia")

        cms_result = {
            "message": "Halaman Tambah SPDP CMS berhasil dibuka.",
            "http_status": 200,
            "url": "http://cms.test/pidum/spdp/create",
            "title": "Tambah SPDP",
            "form_found": True,
            "field_count": 40,
            "session_reused": True,
        }
        with patch("cases.views.cms_service.open_spdp_create", return_value=cms_result) as open_page:
            sync_response = self.client.post(
                reverse("cases:p16_cms_prepare", args=[draft.pk]),
                {"account_user_id": configured.pk},
            )
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(sync_response.json(), cms_result)
        open_page.assert_called_once_with(configured.pk)

    def test_p16_editor_uses_jodit_and_live_folio_preview(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-editor", "kasi-editor@test.id", "rahasia-kuat")
        jaksa = User.objects.create_user("jaksa-editor", "jaksa-editor@test.id", "rahasia-kuat")
        jaksa_tambahan = User.objects.create_user("jaksa-editor-tambahan", "jaksa-editor-tambahan@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        jaksa.roles.add(self.prosecutor_role)
        jaksa_tambahan.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        assignment.prosecutors.add(jaksa)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        response = self.client.get(reverse("cases:p16_draft_detail", args=[draft.pk]))
        self.assertContains(response, "vendor/jodit/jodit.min.js")
        self.assertContains(response, "PRATINJAU LANGSUNG")
        self.assertContains(response, "F4 8,5 × 13 inci")
        self.assertContains(response, "Naskah P-16")
        self.assertContains(response, "Lampiran")
        self.assertContains(response, "data-p16-tab=", count=3)
        self.assertContains(response, "data-p16-rich-editor=", count=10)
        self.assertContains(response, 'data-p16-rich-editor="offense-summary"')
        self.assertContains(response, "Uraian Tindak Pidana")
        self.assertContains(response, "diduga melakukan tindak pidana")
        self.assertContains(response, "Isi angka nomor urut saja")
        self.assertContains(response, "Nomor surat lengkap")
        self.assertContains(response, 'data-p16-number-region="N.1.11"')
        self.assertContains(response, 'data-p16-number-code="Um.1"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "Upload Barcode/QR")
        self.assertContains(response, "Upload barcode verifikasi")
        self.assertContains(response, 'data-p16-barcode-dropzone')
        self.assertContains(response, 'data-p16-barcode-preview')
        self.assertContains(response, 'data-p16-barcode-input')
        self.assertNotContains(response, "Pilih Gambar")
        self.assertContains(response, "Jaksa Penuntut")
        self.assertContains(response, 'data-p16-prosecutor-picker')
        self.assertContains(response, 'data-p16-prosecutor-select')
        self.assertContains(response, 'data-p16-prosecutor-add')
        self.assertContains(response, 'data-status="appointed"')
        self.assertContains(response, 'data-status="additional"')
        self.assertContains(response, 'data-p16-team-body')
        self.assertContains(response, 'data-rank=')
        self.assertContains(response, 'data-nip=')
        self.assertContains(response, 'data-nrp=')
        self.assertContains(response, 'data-p16-tab="administrasi"')
        self.assertContains(response, "Petugas Administrasi")
        self.assertContains(response, "Tambah Petugas")
        self.assertContains(response, 'data-p16-administrative-staff-picker')
        self.assertContains(response, 'data-p16-administrative-staff-select')
        self.assertContains(response, 'data-p16-administrative-staff-add')
        self.assertContains(response, "Cetak Semua Dokumen")
        self.assertContains(response, "Ambil Nomor & Upload SIPede")
        self.assertContains(response, 'data-p16-sipede')
        self.assertContains(response, 'data-p16-sipede-field="sifat"')
        self.assertContains(response, 'data-p16-sipede-field="kode_masalah"')
        self.assertContains(response, 'data-p16-sipede-field="tujuan"')
        self.assertContains(response, 'data-p16-sipede-field="perihal"')
        self.assertContains(response, 'data-sipede-captcha-form')
        self.assertContains(response, "PENUNJUKAN PENUNTUT UMUM UNTUK MENGIKUTI PERKEMBANGAN")
        self.assertContains(response, "p16-letterhead-rule")
        self.assertContains(response, "logo-kejaksaan-p16-transparent.png")
        self.assertNotContains(response, "KEJAKSAAN TINGGI BALI")
        self.assertContains(response, 'data-p16-section="administration-legal-basis"')
        self.assertContains(response, 'class="p16-administration-copies-content"')
        self.assertContains(response, "Tersangka")
        self.assertContains(response, 'data-add-suspect')
        self.assertContains(response, 'data-suspect-dialog')
        self.assertContains(response, 'name="suspects-TOTAL_FORMS"')
        self.assertContains(response, 'data-p16-suspect-output')
        content = response.content.decode()
        self.assertLess(content.index("Identitas Surat"), content.index("Jaksa Penuntut"))
        self.assertLess(content.index("Jaksa Penuntut"), content.index("Menimbang"))
        self.assertNotContains(response, "Penanda Tangan")
        self.assertNotContains(response, 'name="signatory"')
        self.assertNotContains(response, 'name="subject"')
        self.assertContains(response, "--p16-margin-top:1cm")

    def test_p16_f4_paper_margin_and_verification_mark_layout(self):
        css = Path(settings.BASE_DIR, "static", "css", "p16-document.css").read_text(encoding="utf-8")
        self.assertIn("size: 8.5in 13in", css)
        self.assertIn("padding: var(--p16-margin-top,1cm)", css)
        self.assertIn(".app-footer", css)
        self.assertIn("--p16-content-center-offset: -0.045cm", css)
        self.assertIn(".p16-administration-copies-content", css)
        self.assertIn(".p16-admin-staff-list.single", css)
        self.assertIn(".p16-copies.p16-administration-copies", css)
        self.assertIn("margin-top: 6pt", css)
        self.assertIn("text-align: left", css)
        self.assertIn("page-break-inside: avoid", css)
        self.assertIn("var(--p16-barcode-bottom-lift,1.5mm)", css)
        self.assertIn('.p16-order-table [data-p16-section="instruction"] > ol', css)
        self.assertIn('.p16-order-table [data-p16-section="recipient"]', css)
        self.assertIn("list-style: decimal outside !important", css)
        self.assertNotIn(".p16-order-table li::before", css)
        self.assertIn("line-height: 1.15", css)
        self.assertIn('[data-p16-section="consideration"]', css)
        self.assertIn("text-align: justify", css)
        self.assertIn(".p16-offense-summary", css)
        self.assertIn("var(--p16-body-indent,117.2pt)", css)
        self.assertIn("grid-template-columns: 16pt 95.3pt 11.8pt minmax(0, 1fr)", css)
        self.assertIn("font-weight: 700", css)
        self.assertIn("solid #111", css)
        self.assertIn("border-bottom: 0", css)
        self.assertIn("margin-bottom:", css)
        self.assertIn("background: transparent", css)
        self.assertIn("z-index: 3", css)
        self.assertIn("calc(var(--p16-logo-offset-y,0cm) - 0.55cm)", css)
        self.assertIn("calc(var(--p16-header-font-size,10pt) + 2pt)", css)
        self.assertIn("grid-column: 1 / -1", css)
        self.assertIn("calc(var(--p16-header-offset-x,0cm) +", css)
        self.assertIn("calc(var(--p16-letterhead-height,2.68cm) - 0.35cm)", css)
        self.assertIn("calc(var(--p16-logo-width,3.35cm) - 0.70cm)", css)
        self.assertIn(".p16-paper-frame:not(.active)", css)
        self.assertIn("display: block !important", css)
        self.assertIn("page-break-after: always", css)
        self.assertNotIn("size: 8.5in 14in", css)

    @patch("cases.sipede_p16.acquire_number")
    def test_p16_sipede_acquires_number_and_updates_draft(self, acquire_number):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-sipede", "kasi-sipede@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        acquire_number.return_value = {
            "number": "PRINT-1169/N.1.11/Um.1/10/2026",
            "signatory_name": "DICKY DARMAWAN, S.H., M.H.",
            "issue_code": "Um.1",
        }

        with patch("cases.sipede_p16.session_available") as session_available:
            session_response = self.client.post(
                reverse("cases:p16_sipede_upload", args=[draft.pk]), {"action": "session"},
            )
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(session_response.json()["session_active"])
        session_available.assert_called_once()

        response = self.client.post(
            reverse("cases:p16_sipede_upload", args=[draft.pk]),
            {
                "action": "number",
                "sifat": "B",
                "kode_masalah": "Eoh.1",
                "tujuan": "KEPALA KEJAKSAAN NEGERI BULELENG",
                "perihal": "PERIHAL HASIL EDIT",
            },
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["number"], "PRINT-1169/N.1.11/Um.1/10/2026")
        draft.refresh_from_db()
        self.assertEqual(draft.draft_number, "PRINT-1169/N.1.11/Um.1/10/2026")
        self.assertIn(draft.draft_number, draft.content_html)
        self.assertEqual(acquire_number.call_args.kwargs, {
            "sifat": "B", "issue_code": "Eoh.1",
        })

    @patch("cases.sipede_p16.upload_document")
    def test_p16_sipede_upload_marks_draft_as_uploaded(self, upload_document):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-sipede-upload", "kasi-sipede-upload@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        draft.draft_number = "PRINT-1170/N.1.11/Um.1/10/2026"
        draft.save(update_fields=("draft_number", "updated_at"))
        session = self.client.session
        session[f"p16_sipede_number_{draft.pk}"] = draft.draft_number
        session[f"p16_sipede_payload_{draft.pk}"] = {
            "sifat": "PRIN",
            "issue_code": "Eoh.1",
            "destination": "TUJUAN HASIL EDIT",
            "subject": "PERIHAL HASIL EDIT",
        }
        session.save()
        upload_document.return_value = {"number": draft.draft_number}

        response = self.client.post(
            reverse("cases:p16_sipede_upload", args=[draft.pk]),
            {"action": "upload", "document_html": "<article class='p16-paper'></article>"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uploaded"])
        draft.refresh_from_db()
        self.assertEqual(draft.sipede_status, P16Draft.SipedeStatus.UPLOADED)
        self.assertIsNotNone(draft.sipede_uploaded_at)
        self.assertEqual(upload_document.call_args.kwargs, {
            "sifat": "PRIN",
            "issue_code": "Eoh.1",
            "destination": "TUJUAN HASIL EDIT",
            "subject": "PERIHAL HASIL EDIT",
        })

    def test_p16_editor_can_save_multiple_administrative_staff(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-admin-staff", "kasi-admin-staff@test.id", "rahasia-kuat")
        prosecutor = User.objects.create_user("jaksa-admin-staff", "jaksa-admin-staff@test.id", "rahasia-kuat")
        staff_one = User.objects.create_user("staff-admin-satu", "staff-admin-satu@test.id", "rahasia-kuat")
        staff_two = User.objects.create_user("staff-admin-dua", "staff-admin-dua@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        prosecutor.roles.add(self.prosecutor_role)
        staff_one.roles.add(self.employee_role)
        staff_two.roles.add(self.employee_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(prosecutor)
        assignment.appointed_prosecutors.add(prosecutor)
        assignment.administrative_staff.add(staff_one)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        self.assertIn('class="p16-admin-staff-list single"', draft.content_html)

        response = self.client.post(
            reverse("cases:p16_draft_detail", args=[draft.pk]),
            self.p16_payload(draft, administrative_staff=[str(staff_one.pk), str(staff_two.pk)]),
        )

        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        assignment.refresh_from_db()
        self.assertEqual(
            set(assignment.administrative_staff.values_list("pk", flat=True)),
            {staff_one.pk, staff_two.pk},
        )
        draft.refresh_from_db()
        self.assertNotIn('class="p16-admin-staff-list single"', draft.content_html)
        self.assertIn(staff_one.display_name.upper(), draft.content_html)
        self.assertIn(staff_two.display_name.upper(), draft.content_html)

    def test_p16_editor_sanitizes_html_before_saving(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-safe", "kasi-safe@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        unsafe = '<p onclick="alert(1)">Isi aman</p><script>alert(2)</script><img src="javascript:alert(3)">'
        payload = self.p16_payload(
            draft,
            consideration_html=unsafe,
            offense_summary_html='<p onclick="alert(4)">Uraian tindak pidana diperbarui.</p>',
            letter_date="2026-09-03",
        )
        response = self.client.post(reverse("cases:p16_draft_detail", args=[draft.pk]), payload)
        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertIn("Isi aman", draft.content_html)
        self.assertNotIn("onclick", draft.content_html)
        self.assertNotIn("script", draft.content_html)
        self.assertNotIn("javascript:", draft.content_html)
        self.assertEqual(draft.offense_summary_html, "<p>Uraian tindak pidana diperbarui.</p>")
        self.assertIn("Uraian tindak pidana diperbarui.", draft.content_html)
        self.assertIn('data-p16-group="naskah"', draft.content_html)
        self.assertEqual(draft.last_edited_by, self.user)

    def test_p16_editor_uploads_barcode_image_to_preview(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-barcode", "kasi-barcode@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        barcode = SimpleUploadedFile(
            "barcode.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        payload = self.p16_payload(draft, barcode_image=barcode)
        response = self.client.post(reverse("cases:p16_draft_detail", args=[draft.pk]), payload)
        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertTrue(draft.barcode_image.name.startswith("p16/barcodes/"))
        self.assertIn("has-barcode", draft.content_html)
        self.assertIn(draft.barcode_image.url, draft.content_html)

    def test_p16_editor_builds_complete_number_and_adds_prosecutor(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-structured", "kasi-structured@test.id", "rahasia-kuat")
        first = User.objects.create_user("jaksa-awal", "jaksa-aw0@test.id", "rahasia-kuat")
        additional = User.objects.create_user("jaksa-tambahan", "jaksa-tambahan@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        first.roles.add(self.prosecutor_role)
        additional.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(first)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        payload = self.p16_payload(
            draft,
            draft_number="1169",
            letter_date="2026-07-03",
            prosecutors=[str(first.pk), str(additional.pk)],
        )
        response = self.client.post(reverse("cases:p16_draft_detail", args=[draft.pk]), payload)
        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertFalse(draft.manual_number)
        self.assertEqual(draft.draft_number, "PRINT-1169/N.1.11/Um.1/07/2026")
        self.assertIsNone(draft.signatory)
        self.assertEqual(set(assignment.prosecutors.values_list("pk", flat=True)), {first.pk, additional.pk})
        self.assertEqual(set(assignment.appointed_prosecutors.values_list("pk", flat=True)), {first.pk})

    def test_p16_editor_can_remove_appointed_prosecutor_and_rebuild_attachment(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-team-editor", "kasi-team-editor@test.id", "rahasia-kuat")
        first = User.objects.create_user("jaksa-hapus", "jaksa-hapus@test.id", "rahasia-kuat")
        replacement = User.objects.create_user("jaksa-pengganti", "jaksa-pengganti@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        first.roles.add(self.prosecutor_role)
        replacement.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(first)
        assignment.appointed_prosecutors.add(first)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)

        response = self.client.post(
            reverse("cases:p16_draft_detail", args=[draft.pk]),
            self.p16_payload(draft, prosecutors=[str(replacement.pk)]),
        )

        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(set(assignment.prosecutors.values_list("pk", flat=True)), {replacement.pk})
        self.assertEqual(set(assignment.appointed_prosecutors.values_list("pk", flat=True)), {first.pk})
        self.assertNotIn(first.display_name.upper(), draft.content_html)
        self.assertIn(replacement.display_name.upper(), draft.content_html)

    def test_p16_editor_can_edit_and_add_suspects(self):
        spdp = self.create_spdp()
        existing = spdp.suspects.get()
        existing.name = "Nama Lama"
        existing.save(update_fields=("name",))
        kasi = User.objects.create_user("kasi-suspect-editor", "kasi-suspect-editor@test.id", "rahasia-kuat")
        prosecutor = User.objects.create_user("jaksa-suspect-editor", "jaksa-suspect-editor@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        prosecutor.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(prosecutor)
        assignment.appointed_prosecutors.add(prosecutor)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        payload = self.p16_payload(draft)
        payload.update({
            "suspects-TOTAL_FORMS": "2",
            "suspects-INITIAL_FORMS": "1",
            "suspects-MIN_NUM_FORMS": "0",
            "suspects-MAX_NUM_FORMS": "1000",
            "suspects-0-id": str(existing.pk),
            "suspects-0-name": "Nama Diperbarui",
            "suspects-0-suspect_type": "TERSANGKA",
            "suspects-0-nationality": "Indonesia",
            "suspects-1-id": "",
            "suspects-1-name": "Tersangka Baru",
            "suspects-1-suspect_type": "TERSANGKA",
            "suspects-1-birth_date": "2000-01-15",
            "suspects-1-nationality": "Indonesia",
        })

        response = self.client.post(reverse("cases:p16_draft_detail", args=[draft.pk]), payload)

        self.assertRedirects(response, reverse("cases:p16_draft_detail", args=[draft.pk]))
        names = list(spdp.suspects.order_by("sequence").values_list("name", flat=True))
        self.assertEqual(names, ["Nama Diperbarui", "Tersangka Baru"])
        self.assertEqual(spdp.suspects.get(name="Tersangka Baru").age, 26)
        draft.refresh_from_db()
        self.assertIn("Nama Diperbarui", draft.content_html)
        self.assertIn("Tersangka Baru", draft.content_html)

    def test_p16_number_rejects_invalid_sequence(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-auto-number", "kasi-auto-number@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        payload = self.p16_payload(draft, draft_number="NOMOR-BUKAN-ANGKA")
        response = self.client.post(reverse("cases:p16_draft_detail", args=[draft.pk]), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nomor urut harus berupa angka dan boleh memiliki satu huruf di belakang.")
        draft.refresh_from_db()
        self.assertFalse(draft.manual_number)
        self.assertTrue(draft.draft_number.startswith("DRAFT/P-16/"))

    def test_unrelated_user_cannot_edit_p16_draft(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-owner", "kasi-owner@test.id", "rahasia-kuat")
        outsider = User.objects.create_user("outsider", "outsider@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        self.client.force_login(outsider)
        response = self.client.post(reverse("cases:p16_draft_detail", args=[draft.pk]), {
            "draft_number": draft.draft_number, "letter_date": "2026-09-03",
            "subject": "Tidak boleh", "content_html": "<p>Ubah</p>",
        })
        self.assertEqual(response.status_code, 403)

    def test_employee_without_assignment_cannot_edit_p16_draft(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-employee-check", "kasi-employee-check@test.id", "rahasia-kuat")
        jaksa = User.objects.create_user("jaksa-employee-check", "jaksa-employee-check@test.id", "rahasia-kuat")
        employee = User.objects.create_user("pegawai-employee-check", "pegawai-employee-check@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        jaksa.roles.add(self.prosecutor_role)
        employee.roles.add(self.employee_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(jaksa)
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        self.client.force_login(employee)
        response = self.client.post(
            reverse("cases:p16_draft_detail", args=[draft.pk]),
            {
                "draft_number": draft.draft_number,
                "letter_date": draft.letter_date.isoformat(),
                "subject": draft.subject,
                "content_html": draft.content_html,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_action_is_dropdown_and_workflow_uses_dialog(self):
        self.create_spdp()
        response = self.client.get(reverse("cases:spdp_list"))
        self.assertContains(response, 'class="action-menu workflow-row-actions"')
        self.assertContains(response, "Proses P-16")
        self.assertContains(response, 'class="workflow-modal"')
        self.assertContains(response, "workflow.css")
        self.assertContains(response, "p16-workflow.js?v=20261124-1")
        html = response.content.decode()
        self.assertGreater(html.index('id="start-p16-dialog"'), html.index("</table>"))
        workflow_script = Path(
            settings.BASE_DIR, "static", "js", "p16-workflow.js",
        ).read_text(encoding="utf-8")
        self.assertIn("function closeActionMenus()", workflow_script)
        self.assertIn("closeActionMenus();", workflow_script)
        self.assertNotIn("closeMenus();", workflow_script)

    def test_spdp_list_shows_p16_deadline_remaining_days(self):
        self.create_spdp()
        response = self.client.get(reverse("cases:spdp_list"))
        self.assertContains(response, "Sisa Hari")
        self.assertContains(response, "Batas 05 Agu 2026")
        self.assertContains(response, "Lewat")
        self.assertContains(response, "deadline-badge-value")
        self.assertContains(response, 'class="deadline-badge overdue"')

    def test_deadline_display_formats_remaining_due_and_overdue_days(self):
        deadline = case_deadline_for_spdp(
            self.create_spdp(),
            timezone.localdate(),
        )

        self.assertEqual(
            deadline.remaining_display,
            f"Terlambat {abs(deadline.remaining_days)} hari",
        )
        self.assertEqual(
            replace(deadline, remaining_days=4).remaining_display,
            "Sisa 4 hari",
        )
        self.assertEqual(
            replace(deadline, remaining_days=0).remaining_display,
            "Hari ini",
        )
        self.assertEqual(
            replace(deadline, remaining_days=-2).remaining_display,
            "Terlambat 2 hari",
        )

    def test_spdp_list_shows_summary_cards_and_priority_activity(self):
        spdp = self.create_spdp()
        response = self.client.get(reverse("cases:spdp_list"))
        self.assertContains(response, "Total Perkara")
        self.assertContains(response, f"Tahun {timezone.localdate().year}")
        self.assertContains(response, "Bulan ")
        self.assertContains(response, "Hari Ini")
        self.assertNotContains(response, "berjalan")
        self.assertContains(response, "Harus Diselesaikan")
        self.assertContains(response, "1 prioritas")
        self.assertContains(response, spdp.letter_number)
        self.assertContains(response, "Terbitkan P-16 sebelum 05 Agu 2026")
        self.assertContains(response, "case-priority-overdue")
        self.assertContains(response, "case-priority-quick-actions")
        self.assertContains(response, "Proses P-16")
        self.assertContains(response, "Notif")

    def test_spdp_status_tracks_the_active_stage_and_draft(self):
        spdp = self.create_spdp()
        response = self.client.get(reverse("cases:spdp_list"))
        self.assertContains(response, "Menunggu P-16")

        kasi = User.objects.create_user("kasi-status", "kasi-status@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.WAITING_PROSECUTOR,
        )
        spdp.status = SPDP.Status.PROCESS
        spdp.save(update_fields=("status", "updated_at"))
        response = self.client.get(reverse("cases:spdp_list"))
        self.assertContains(response, "Proses P-16")
        self.assertContains(response, "Menunggu penunjukan Jaksa")

        assignment.status = P16Assignment.Status.ASSIGNED
        assignment.save(update_fields=("status",))
        p16, _ = P16Draft.create_for_assignment(assignment, kasi)
        p16.draft_number = "B/16/N.1.11/Um/2026"
        p16.save(update_fields=("draft_number", "updated_at"))
        p17 = P17Draft.create_for_spdp(spdp, self.user)

        response = self.client.get(reverse("cases:spdp_list"))
        self.assertContains(response, "Proses P-17")
        self.assertContains(response, "Draf P-17")
        detail = self.client.get(reverse("cases:spdp_detail", args=[spdp.pk]))
        self.assertContains(detail, "Proses P-17")

    def test_spdp_history_lists_issued_documents_in_workflow_order(self):
        spdp = self.create_spdp()
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=self.user,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        p16 = P16Draft.objects.create(
            assignment=assignment,
            draft_number="B/P-16/HISTORY/2026",
            letter_date=timezone.localdate(),
        )
        p17 = P17Draft.create_for_spdp(spdp, self.user)
        p17.letter_number = "B/P-17/HISTORY/2026"
        p17.save(update_fields=("letter_number", "updated_at"))
        P17Draft.create_for_spdp(spdp, self.user)
        sop02 = SOPForm02Draft.objects.create(
            spdp=spdp,
            letter_number="B/SOP-02/HISTORY/2026",
            letter_date=timezone.localdate(),
        )
        sop03 = SOPForm03Draft.objects.create(
            spdp=spdp,
            letter_number="B/SOP-03/HISTORY/2026",
            letter_date=timezone.localdate(),
        )
        StageOne.objects.create(
            spdp=spdp,
            case_file_number="BP/01/HISTORY/2026",
            cover_letter_number="B/01/HISTORY/2026",
            laws_and_articles="Pasal 362 KUHP",
            cover_letter_document="stage-one/history.pdf",
            created_by=self.user,
        )
        case_documents = (
            (CaseDocumentDraft.DocumentType.P18, "B/P-18/HISTORY/2026"),
            (CaseDocumentDraft.DocumentType.P19, "B/P-19/HISTORY/2026"),
            (CaseDocumentDraft.DocumentType.P20, "B/P-20/HISTORY/2026"),
            (CaseDocumentDraft.DocumentType.SOP_FORM_07, "B/SOP-07/HISTORY/2026"),
        )
        for document_type, letter_number in case_documents:
            CaseDocumentDraft.objects.create(
                spdp=spdp,
                document_type=document_type,
                letter_number=letter_number,
                letter_date=timezone.localdate(),
            )
        p21 = P21Draft.create_for_spdp(spdp, self.user)
        p21.letter_number = "B/P-21/HISTORY/2026"
        p21.status = P21Draft.Status.COMPLETED
        p21.save(update_fields=("letter_number", "status", "updated_at"))

        response = self.client.get(reverse("cases:spdp_detail", args=[spdp.pk]))

        self.assertEqual(
            [item["title"] for item in response.context["history"]],
            [
                "SPDP diterima",
                "P-16 diterbitkan",
                "P-17 Permintaan Pertama",
                "SOP Form 2 diterbitkan",
                "SOP Form 3 diterbitkan",
                "Tahap 1 diterima",
                "P-18 diterbitkan",
                "P-19 diterbitkan",
                "P-20 diterbitkan",
                "P-21 diterbitkan",
                "SOP Form 7 diterbitkan",
            ],
        )
        self.assertNotContains(response, "DRAFT/P-17")
        self.assertContains(response, "Sudah dilaksanakan")

    def test_spdp_activity_warns_from_h_minus_two(self):
        spdp = self.create_spdp()
        today = timezone.localdate()
        SPDP.objects.filter(pk=spdp.pk).update(
            investigation_order_date=today - timedelta(days=2),
            letter_date=today - timedelta(days=1),
            received_date=today,
        )

        response = self.client.get(reverse("cases:spdp_list"))

        self.assertContains(response, "Segera 2 hari", count=1)
        self.assertContains(response, 'class="deadline-badge warning"', count=2)
        self.assertContains(response, "1 prioritas")

    def test_assign_action_disappears_and_reassignment_is_blocked(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-final", "kasi-final@test.id", "rahasia-kuat")
        jaksa = User.objects.create_user("jaksa-final", "jaksa-final@test.id", "rahasia-kuat")
        jaksa_lain = User.objects.create_user("jaksa-lain", "jaksa-lain@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        jaksa.roles.add(self.prosecutor_role)
        jaksa_lain.roles.add(self.prosecutor_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(jaksa)
        self.client.force_login(kasi)

        page = self.client.get(reverse("cases:spdp_list"))
        self.assertNotContains(page, "Tunjuk Jaksa")
        self.assertContains(page, "P-16 Diproses")

        response = self.client.post(
            reverse("cases:assign_prosecutors", args=[spdp.pk]),
            {"prosecutors": [jaksa_lain.pk]},
            follow=True,
        )
        self.assertContains(response, "tidak dapat ditunjuk ulang")
        self.assertEqual(set(assignment.prosecutors.values_list("pk", flat=True)), {jaksa.pk})

    def test_p17_menu_and_list_are_available(self):
        response = self.client.get(reverse("cases:p17_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daftar P-17")
        self.assertContains(response, 'href="%s"' % reverse("cases:p17_list"))
        self.assertContains(response, "Belum ada draf P-17")

    def test_p16_card_style_is_shared_except_on_selected_lists(self):
        matching_lists = (
            "p16_list",
            "p17_list",
            "p21_list",
            "sop_form_02_list",
            "p19_list",
            "stage_one_list",
            "spdp_list",
        )
        excluded_lists = (
            "p18_list",
            "p20_list",
            "sop_form_03_list",
            "sop_form_07_list",
        )
        for list_name in matching_lists:
            with self.subTest(list_name=list_name):
                response = self.client.get(reverse(f"cases:{list_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "css/spdp-list.css")
        for list_name in excluded_lists:
            with self.subTest(list_name=list_name):
                response = self.client.get(reverse(f"cases:{list_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "css/spdp-list.css")

    def test_create_p17_from_spdp_with_p16(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p17", "kasi-p17@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        P16Draft.create_for_assignment(assignment, kasi)

        response = self.client.post(reverse("cases:p17_create"), {"spdp": spdp.pk})

        draft = P17Draft.objects.get(spdp=spdp)
        self.assertRedirects(response, reverse("cases:p17_draft_detail", args=[draft.pk]))
        self.assertEqual(draft.sequence, 1)
        self.assertTrue(draft.letter_number.startswith("DRAFT/P-17/"))
        self.assertIn(spdp.letter_number, draft.body_html)
        self.assertIn("Permintaan Perkembangan Hasil Penyidikan", draft.subject_html)
        self.assertIn("A r s i p.", draft.copies_html)

    def test_p17_editor_has_three_sections_and_live_folio_preview(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p17-editor", "kasi-p17-editor@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        P16Draft.create_for_assignment(assignment, kasi)
        draft = P17Draft.create_for_spdp(spdp, self.user)

        response = self.client.get(reverse("cases:p17_draft_detail", args=[draft.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Identitas Surat")
        self.assertContains(response, ">Isi<")
        self.assertContains(response, "Tembusan")
        self.assertContains(response, "vendor/jodit/jodit.min.js")
        self.assertContains(response, "PRATINJAU LANGSUNG")
        self.assertContains(response, "8,5 × 13 inci")
        self.assertContains(response, "data-p17-rich-editor=", count=2)
        self.assertContains(response, "data-p17-subject")
        self.assertContains(response, "Perihal surat")
        self.assertContains(response, "data-p17-add-recipient")
        self.assertContains(response, "data-p17-recipients-json")
        self.assertContains(response, "data-p17-recipient-place")
        self.assertContains(response, 'value="&lt;div class=&quot;p17-recipient-list&quot;')
        self.assertNotContains(response, 'value="<div class="p17-recipient-list"')
        self.assertContains(response, "data-p17-barcode-dropzone")
        self.assertContains(response, "data-p17-print")
        self.assertContains(response, "data-p17-pages")
        self.assertContains(response, "Tanda tangan elektronik")
        self.assertContains(response, "TUJUAN (YTH.)")
        self.assertContains(response, "P-17")
        self.assertContains(response, 'class="p17-letterhead p16-standard-letterhead"')
        self.assertContains(response, 'class="sop1b-letterhead p16-standard-letterhead"')
        self.assertContains(response, "logo-kejaksaan-p16-transparent.png", count=2)
        self.assertContains(response, "p17-document.css")
        self.assertContains(response, "SOP Form-1B")
        self.assertContains(response, 'data-document-tab="sop1b"')
        self.assertContains(response, 'data-document-preview="sop1b"')
        self.assertContains(response, "data-sop1b-rich-editor=", count=6)
        self.assertContains(response, "data-sop1b-pages")
        self.assertContains(response, "data-sop1b-barcode-input")
        self.assertContains(response, "verification-code-placeholder")
        self.assertContains(response, "LAPORAN PENUNTUT UMUM")
        self.assertTrue(SOPForm1BDraft.objects.filter(p17_draft=draft).exists())

    def test_p17_sipede_upload_matches_administrasi_perkara_form(self):
        spdp = self.create_spdp()
        draft = P17Draft.create_for_spdp(spdp, self.user)
        context = MagicMock()
        response = MagicMock(ok=True, url="https://sipede.kejaksaan.go.id/administrasiperkara")
        response.text.return_value = "Berhasil"
        context.request.post.return_value = response
        form_context = {
            "csrf_token": "csrf-test",
            "create_url": "https://sipede.kejaksaan.go.id/administrasiperkara/create?idSurat=7",
            "form_action": "https://sipede.kejaksaan.go.id/administrasiperkara",
            "sifat_options": [{"value": "B", "label": "Biasa"}],
        }
        lifecycle = {"active": False}

        class PlaywrightManager:
            def __enter__(self):
                lifecycle["active"] = True
                return object()

            def __exit__(self, *_args):
                lifecycle["active"] = False

        browser = MagicMock()
        browser.close.side_effect = lambda: self.assertTrue(
            lifecycle["active"], "Browser harus ditutup sebelum Playwright berhenti."
        )

        def metadata_targets(*_args, **_kwargs):
            self.assertFalse(
                lifecycle["active"], "ORM metadata harus dibaca sebelum Playwright aktif."
            )
            return {
                "signatory_name": "Penandatangan uji",
                "configured_issue_code": "Uji.1",
                "sender": "Kepala Kejaksaan Negeri Contoh",
            }

        with (
            patch("playwright.sync_api.sync_playwright", return_value=PlaywrightManager()),
            patch("cases.sipede_p17._integration_and_session", return_value=(MagicMock(), {})),
            patch("cases.sipede_p17._render_pdf", return_value=b"%PDF-1.4"),
            patch("cases.sipede_p17._open_form", return_value=(browser, context, None, form_context)),
            patch("cases.sipede_p17._metadata_targets", side_effect=metadata_targets),
            patch("cases.sipede_p17._resolved_metadata", return_value={
                "issue_code": "Uji.1", "signatory_id": "1001", "sender": "Kepala Kejaksaan Negeri Contoh",
            }),
            patch("cases.sipede_p17._persist"),
        ):
            from cases.sipede_p17 import upload_document

            upload_document(
                self.user,
                draft,
                f'<p data-p17-output="number">{draft.letter_number}</p>',
                destination="Tujuan surat uji",
                subject="Perihal surat uji",
                disposition_ids=["98765"],
            )

        multipart = context.request.post.call_args.kwargs["multipart"]
        self.assertEqual(set(multipart), {
            "_token", "nomor", "tanggal", "sifat", "kode_masalah", "dari", "tujuan",
            "hal", "src", "lampiran", "penandatangan", "idSurat", "tujuan_surat",
            "submitModal",
        })
        self.assertEqual(multipart["idSurat"], "7")
        self.assertEqual(multipart["tujuan_surat"], "98765")
        self.assertEqual(multipart["submitModal"], "ok")
        self.assertEqual(multipart["src"]["mimeType"], "application/pdf")
        self.assertEqual(multipart["lampiran"], {
            "name": "", "mimeType": "application/octet-stream", "buffer": b"",
        })
        browser.close.assert_called_once_with()

    def test_sipede_opens_suratkeluar_form_for_new_document_route(self):
        browser, context, page = MagicMock(), MagicMock(), MagicMock()
        page.url = "https://sipede.kejaksaan.go.id/suratkeluar/create?idSurat=125"
        form_context = {
            "csrf_token": "csrf-test",
            "form_action": "https://sipede.kejaksaan.go.id/suratkeluar",
        }
        with (
            patch("configurations.sipede._open_browser", return_value=(browser, context, page)),
            patch("cases.sipede_p17._restore_cookies"),
            patch("cases.sipede_p17._read_form_context", return_value=form_context),
        ):
            from cases.sipede_p17 import _open_form

            _browser, _context, _page, result = _open_form(
                object(),
                {"cookies": []},
                id_surat="125",
                document_label="P-19",
                form_route="suratkeluar",
            )

        page.goto.assert_called_once_with(
            "https://sipede.kejaksaan.go.id/suratkeluar/create?idSurat=125",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        self.assertEqual(result["form_action"], "https://sipede.kejaksaan.go.id/suratkeluar")
        self.assertEqual(result["form_route"], "suratkeluar")

    def test_suratkeluar_number_flow_checks_auto_number(self):
        spdp = self.create_spdp()
        draft = P17Draft.create_for_spdp(spdp, self.user)
        browser, context = MagicMock(), MagicMock()
        signatory_response = MagicMock(ok=True, status=200)
        signatory_response.json.return_value = {
            "results": [{"id": "1001", "text": "Dicky Darmawan"}],
        }
        auto_number_response = MagicMock(ok=True, status=200)
        context.request.get.side_effect = [signatory_response, auto_number_response]
        number_response = MagicMock(ok=True, status=200)
        number_response.text.return_value = "4711"
        context.request.post.return_value = number_response
        form_context = {
            "csrf_token": "csrf-test",
            "create_url": "https://sipede.kejaksaan.go.id/suratkeluar/create?idSurat=125",
            "form_route": "suratkeluar",
            "jenis": "14",
            "jenis_options": [{"value": "100", "label": "BIASA INTERNAL / EKSTERNAL"}],
            "sifat_options": [{"value": "B", "label": "Biasa"}],
            "kode_masalah_options": [{"value": "Uji.1", "label": "Uji.1"}],
        }
        manager = MagicMock()
        manager.__enter__.return_value = object()
        manager.__exit__.return_value = False

        with (
            patch("playwright.sync_api.sync_playwright", return_value=manager),
            patch("cases.sipede_p17._integration_and_session", return_value=(MagicMock(), {})),
            patch("cases.sipede_p17._metadata_targets", return_value={
                "signatory_name": "Dicky Darmawan, S.H., M.H.",
                "configured_issue_code": "Uji.1",
                "sender": "Kepala Kejaksaan Negeri Contoh",
            }),
            patch("cases.sipede_p17._open_form", return_value=(browser, context, None, form_context)),
            patch("cases.sipede_p17._persist"),
        ):
            from cases.sipede_p17 import acquire_number

            result = acquire_number(
                self.user,
                draft,
                sifat="B",
                issue_code="Uji.1",
                id_surat="125",
                document_label="P-19",
                form_route="suratkeluar",
                jenis_surat="100",
            )

        self.assertEqual(context.request.get.call_count, 2)
        signatory_call, auto_number_call = context.request.get.call_args_list
        self.assertEqual(
            signatory_call.args[0],
            "https://sipede.kejaksaan.go.id/suratkeluar/list-penandatangan-ajax",
        )
        self.assertEqual(signatory_call.kwargs["params"], {"q": "Dicky Darmawan, S.H., M.H."})
        self.assertEqual(
            auto_number_call.args[0],
            "https://sipede.kejaksaan.go.id/suratkeluar/check-auto-number",
        )
        self.assertEqual(auto_number_call.kwargs["params"], {"surat": "100"})
        self.assertEqual(result["number"], "4711")
        self.assertEqual(result["jenis_surat"], "100")
        self.assertEqual(context.request.post.call_args.kwargs["form"]["penandatangan"], "1001")
        self.assertEqual(context.request.post.call_args.kwargs["form"]["jenis_surat"], "100")
        browser.close.assert_called_once_with()

    def test_suratkeluar_upload_posts_to_captured_form_action(self):
        spdp = self.create_spdp()
        draft = P17Draft.create_for_spdp(spdp, self.user)
        browser, context = MagicMock(), MagicMock()
        signatory_response = MagicMock(ok=True, status=200)
        signatory_response.json.return_value = {
            "results": [{"id": "1001", "text": "Dicky Darmawan"}],
        }
        context.request.get.return_value = signatory_response
        context.request.post.return_value = MagicMock(
            ok=True,
            url="https://sipede.kejaksaan.go.id/suratkeluar",
        )
        form_context = {
            "csrf_token": "csrf-test",
            "create_url": "https://sipede.kejaksaan.go.id/suratkeluar/create?idSurat=125",
            "form_action": "https://sipede.kejaksaan.go.id/suratkeluar",
            "form_route": "suratkeluar",
            "sifat_options": [{"value": "B", "label": "Biasa"}],
            "jenis_options": [{"value": "100", "label": "BIASA INTERNAL / EKSTERNAL"}],
            "kode_masalah_options": [{"value": "Uji.1", "label": "Uji.1"}],
        }
        manager = MagicMock()
        manager.__enter__.return_value = object()
        manager.__exit__.return_value = False

        with (
            patch("playwright.sync_api.sync_playwright", return_value=manager),
            patch("cases.sipede_p17._integration_and_session", return_value=(MagicMock(), {})),
            patch("cases.sipede_p17._render_pdf", return_value=b"%PDF-1.4"),
            patch("cases.sipede_p17._open_form", return_value=(browser, context, None, form_context)) as open_form,
            patch("cases.sipede_p17._metadata_targets", return_value={
                "signatory_name": "Dicky Darmawan, S.H., M.H.",
                "configured_issue_code": "Uji.1",
                "sender": "Kepala Kejaksaan Negeri Contoh",
            }),
            patch("cases.sipede_p17._persist"),
        ):
            from cases.sipede_p17 import upload_document

            upload_document(
                self.user,
                draft,
                f'<p data-document-output="number">{draft.letter_number}</p>',
                destination="Tujuan surat uji",
                subject="Perihal surat uji",
                disposition_ids=["98765"],
                signatory_name="Dicky Darmawan, S.H., M.H.",
                id_surat="125",
                document_label="P-19",
                form_route="suratkeluar",
                jenis_surat="100",
            )

        open_form.assert_called_once_with(
            ANY,
            ANY,
            id_surat="125",
            document_label="P-19",
            form_route="suratkeluar",
        )
        args, kwargs = context.request.post.call_args
        self.assertEqual(args[0], "https://sipede.kejaksaan.go.id/suratkeluar")
        self.assertEqual(kwargs["headers"]["Referer"], form_context["create_url"])
        self.assertEqual(kwargs["multipart"]["idSurat"], "125")
        self.assertEqual(kwargs["multipart"]["jenis"], "100")
        self.assertEqual(kwargs["multipart"]["tujuan_surat"], "98765")
        self.assertEqual(kwargs["multipart"]["penandatangan"], "1001")
        self.assertEqual(kwargs["multipart"]["upload"]["mimeType"], "application/pdf")
        self.assertNotIn("src", kwargs["multipart"])
        self.assertNotIn("lampiran", kwargs["multipart"])
        self.assertEqual(
            context.request.get.call_args.args[0],
            "https://sipede.kejaksaan.go.id/suratkeluar/list-penandatangan-ajax",
        )
        browser.close.assert_called_once_with()

    @patch("cases.sipede_p17.upload_document")
    def test_sop_form_02_sipede_upload_uses_administrasi_perkara_flow(self, upload_document):
        spdp = self.create_spdp()
        draft = SOPForm02Draft.create_for_spdp(spdp, self.user)
        upload_document.return_value = {"number": draft.letter_number}
        session = self.client.session
        session[f"sop_02_sipede_number_{draft.pk}"] = draft.letter_number
        session[f"sop_02_sipede_payload_{draft.pk}"] = {
            "sifat": "B",
            "issue_code": "Uji.1",
            "destination": "Tujuan surat uji",
            "subject": "Perihal surat uji",
            "signatory_name": "Penandatangan uji",
        }
        session.save()

        response = self.client.post(
            reverse("cases:sop_form_02_sipede_upload", args=[draft.pk]),
            {
                "action": "upload",
                "document_html": f'<p data-sop-output="number">{draft.letter_number}</p>',
                "disposition_ids": ["98765"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uploaded"])
        self.assertEqual(upload_document.call_args.kwargs["id_surat"], settings.SIPEDE_SOP_FORM_02_ID)
        self.assertEqual(upload_document.call_args.kwargs["document_label"], "SOP Form 2")
        self.assertEqual(upload_document.call_args.kwargs["disposition_ids"], ["98765"])
        draft.refresh_from_db()
        self.assertEqual(draft.sipede_status, SOPForm02Draft.SipedeStatus.UPLOADED)

    @patch("cases.sipede_p17.upload_document")
    def test_p18_sipede_upload_uses_captured_administrasi_perkara_form(self, upload_document):
        spdp = self.create_spdp()
        draft = CaseDocumentDraft.create_for_spdp(
            spdp, CaseDocumentDraft.DocumentType.P18, self.user,
        )
        upload_document.return_value = {"number": draft.letter_number}
        session = self.client.session
        session[f"sop_p18_sipede_number_{draft.pk}"] = draft.letter_number
        session[f"sop_p18_sipede_payload_{draft.pk}"] = {
            "sifat": "B",
            "issue_code": "Uji.1",
            "destination": "Penyidik",
            "subject": "Pengembalian berkas perkara",
            "signatory_name": "Penandatangan uji",
        }
        session.save()

        response = self.client.post(
            reverse("cases:p18_sipede_upload", args=[draft.pk]),
            {
                "action": "upload",
                "document_html": f'<p data-document-output="number">{draft.letter_number}</p>',
                "disposition_ids": ["98765"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uploaded"])
        self.assertEqual(
            {
                key: upload_document.call_args.kwargs[key]
                for key in ("id_surat", "document_label", "form_route")
            },
            {
                "id_surat": "8",
                "document_label": "P-18",
                "form_route": "administrasiperkara",
            },
        )
        self.assertEqual(upload_document.call_args.kwargs["disposition_ids"], ["98765"])
        draft.refresh_from_db()
        self.assertEqual(draft.sipede_status, CaseDocumentDraft.SipedeStatus.UPLOADED)

    @patch("cases.sipede_p17.upload_document")
    def test_p20_sipede_upload_changes_case_status_to_dismissed(self, upload_document):
        spdp = self.create_spdp()
        draft = CaseDocumentDraft.create_for_spdp(
            spdp, CaseDocumentDraft.DocumentType.P20, self.user,
        )
        draft.letter_number = "B-520/N.1.11/Um.1/11/2026"
        draft.save(update_fields=("letter_number", "updated_at"))
        upload_document.return_value = {"number": draft.letter_number}
        before_upload = self.client.get(reverse("cases:spdp_list"))
        self.assertEqual(
            before_upload.context["spdp_list"][0].workflow_status["label"],
            "Proses P-20",
        )
        session = self.client.session
        session[f"sop_p20_sipede_number_{draft.pk}"] = draft.letter_number
        session[f"sop_p20_sipede_payload_{draft.pk}"] = {
            "sifat": "B",
            "issue_code": "Uji.1",
            "destination": "Penyidik",
            "subject": "Pemberitahuan P-20",
            "signatory_name": "Penandatangan uji",
            "jenis_surat": settings.SIPEDE_SURATKELUAR_JENIS,
        }
        session.save()

        response = self.client.post(
            reverse("cases:p20_sipede_upload", args=[draft.pk]),
            {
                "action": "upload",
                "document_html": f'<p data-document-output="number">{draft.letter_number}</p>',
                "disposition_ids": ["98765"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uploaded"])
        self.assertEqual(upload_document.call_args.kwargs["form_route"], "suratkeluar")
        draft.refresh_from_db()
        self.assertEqual(draft.sipede_status, CaseDocumentDraft.SipedeStatus.UPLOADED)
        after_upload = self.client.get(reverse("cases:spdp_list"))
        self.assertEqual(
            after_upload.context["spdp_list"][0].workflow_status["label"],
            "Diberhentikan",
        )
        self.assertContains(after_upload, 'class="badge red">Diberhentikan</span>')
        p20_page = self.client.get(reverse("cases:p20_list"))
        self.assertContains(p20_page, 'class="badge red">Diberhentikan</span>')

    @patch("cases.sipede_p17.upload_document")
    def test_p21_sipede_upload_uses_captured_administrasi_perkara_form(self, upload_document):
        spdp = self.create_spdp()
        draft = P21Draft.create_for_spdp(spdp, self.user)
        draft.letter_number = "B-521/N.1.11/Um.1/11/2026"
        draft.save(update_fields=("letter_number", "updated_at"))
        upload_document.return_value = {"number": draft.letter_number}
        session = self.client.session
        session[f"sop_p21_sipede_number_{draft.pk}"] = draft.letter_number
        session[f"sop_p21_sipede_payload_{draft.pk}"] = {
            "sifat": "B",
            "issue_code": "Uji.1",
            "destination": "Penyidik",
            "subject": "Pemberitahuan P-21",
            "signatory_name": "Penandatangan uji",
        }
        session.save()

        response = self.client.post(
            reverse("cases:p21_sipede_upload", args=[draft.pk]),
            {
                "action": "upload",
                "document_html": f'<p data-document-output="number">{draft.letter_number}</p>',
                "disposition_ids": ["98765"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uploaded"])
        self.assertEqual(settings.SIPEDE_P21_ID, "9")
        self.assertEqual(
            {
                key: upload_document.call_args.kwargs[key]
                for key in ("id_surat", "document_label", "form_route")
            },
            {
                "id_surat": "9",
                "document_label": "P-21",
                "form_route": "administrasiperkara",
            },
        )
        self.assertEqual(upload_document.call_args.kwargs["disposition_ids"], ["98765"])
        draft.refresh_from_db()
        self.assertEqual(draft.sipede_status, P21Draft.SipedeStatus.UPLOADED)

    def test_p21_completed_action_stops_reminders_and_updates_case_status(self):
        spdp = self.create_spdp()
        draft = P21Draft.create_for_spdp(spdp, self.user)
        today = timezone.localdate()
        draft.letter_number = "B-522/N.1.11/Um.1/11/2026"
        draft.letter_date = today - timedelta(days=15)
        draft.save(update_fields=("letter_number", "letter_date", "updated_at"))
        context_label = f"P-21 | {spdp.letter_number}"
        p21_web_notification = WebNotification.objects.create(
            recipient=self.user,
            kind=WebNotification.Kind.CASE_DEADLINE,
            title="Reminder P-21",
            message="Tindak lanjut P-21",
            context_label=context_label,
            spdp=spdp,
        )
        other_web_notification = WebNotification.objects.create(
            recipient=self.user,
            kind=WebNotification.Kind.CASE_DEADLINE,
            title="Reminder P-20",
            message="Tindak lanjut P-20",
            context_label=f"P-20 | {spdp.letter_number}",
            spdp=spdp,
        )
        queued_p21_notification = NotificationLog.objects.create(
            channel=NotificationLog.Channel.WHATSAPP,
            recipient="628123456789",
            subject="Reminder P-21",
            message="Tindak lanjut P-21",
            status=NotificationLog.Status.QUEUED,
            context_label=context_label,
        )
        queued_other_notification = NotificationLog.objects.create(
            channel=NotificationLog.Channel.TELEGRAM,
            recipient="123456789",
            subject="Reminder P-20",
            message="Tindak lanjut P-20",
            status=NotificationLog.Status.QUEUED,
            context_label=f"P-20 | {spdp.letter_number}",
        )

        deadline = case_deadline_for_spdp(
            SPDP.objects.select_related("p21_draft").get(pk=spdp.pk),
            today,
        )
        self.assertEqual(deadline.stage_key, "p21")
        list_page = self.client.get(reverse("cases:p21_list"))
        self.assertContains(
            list_page,
            reverse("cases:p21_mark_completed", args=[draft.pk]),
        )

        response = self.client.post(
            reverse("cases:p21_mark_completed", args=[draft.pk]),
        )

        self.assertRedirects(response, reverse("cases:p21_list"))
        draft.refresh_from_db()
        self.assertEqual(draft.status, P21Draft.Status.COMPLETED)
        self.assertIsNone(case_deadline_for_spdp(
            SPDP.objects.select_related("p21_draft").get(pk=spdp.pk),
            today,
        ))
        self.assertFalse(WebNotification.objects.filter(pk=p21_web_notification.pk).exists())
        self.assertTrue(WebNotification.objects.filter(pk=other_web_notification.pk).exists())
        queued_p21_notification.refresh_from_db()
        self.assertEqual(queued_p21_notification.status, NotificationLog.Status.CANCELLED)
        queued_other_notification.refresh_from_db()
        self.assertEqual(queued_other_notification.status, NotificationLog.Status.QUEUED)
        self.assertContains(
            self.client.get(reverse("cases:p21_list")),
            '<span class="badge green">Sudah P-21</span>',
        )
        self.assertContains(
            self.client.get(reverse("cases:spdp_list")),
            "Sudah P-21",
        )

    @patch("cases.sipede_p17.upload_document")
    def test_sop_form_03_sipede_upload_marks_issued_and_notifies_case_team(self, upload_document):
        spdp = self.create_spdp()
        draft = SOPForm03Draft.create_for_spdp(spdp, self.user)
        upload_document.return_value = {"number": draft.letter_number}
        session = self.client.session
        session[f"sop_03_sipede_number_{draft.pk}"] = draft.letter_number
        session[f"sop_03_sipede_payload_{draft.pk}"] = {
            "sifat": "B",
            "issue_code": "Uji.1",
            "destination": "Tujuan surat uji",
            "subject": "Perihal surat uji",
            "signatory_name": "Penandatangan uji",
            "jenis_surat": "100",
        }
        session.save()

        with (
            patch("cases.views.send_document_issued_notifications") as notify,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                reverse("cases:sop_form_03_sipede_upload", args=[draft.pk]),
                {
                    "action": "upload",
                    "document_html": f'<p data-sop-output="number">{draft.letter_number}</p>',
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["uploaded"])
        draft.refresh_from_db()
        self.assertEqual(draft.sipede_status, SOPForm03Draft.SipedeStatus.UPLOADED)
        notify.assert_called_once_with(
            spdp_id=spdp.pk,
            stage_key="sop03",
            document_id=draft.pk,
            document_number=draft.letter_number,
            document_date=draft.letter_date,
            actor_id=self.user.pk,
        )
        retry = self.client.post(
            reverse("cases:sop_form_03_sipede_upload", args=[draft.pk]),
            {"action": "upload"},
        )
        self.assertTrue(retry.json()["uploaded"])
        notify.assert_called_once()
        self.assertContains(self.client.get(reverse("cases:sop_form_03_list")), "Terbit")

    def test_p17_editor_saves_sop_form_1b_separately(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-sop-1b", "kasi-sop-1b@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        prosecutor = User.objects.create_user(
            "jaksa-sop-1b", "jaksa-sop-1b@test.id", "rahasia-kuat",
            first_name="I Made Jaksa", rank="Jaksa Muda", nip="198001012005011001",
        )
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        assignment.prosecutors.add(prosecutor)
        P16Draft.create_for_assignment(assignment, kasi)
        draft = P17Draft.create_for_spdp(spdp, self.user)
        self.client.get(reverse("cases:p17_draft_detail", args=[draft.pk]))
        sop_draft = SOPForm1BDraft.objects.get(p17_draft=draft)
        payload = self.p17_payload(draft)
        payload.update({
            "sop1b-report_date": sop_draft.report_date.isoformat(),
            "sop1b-recipient": "Kepala Kejaksaan Negeri Buleleng",
            "sop1b-sender": sop_draft.sender,
            "sop1b-attachment": sop_draft.attachment,
            "sop1b-subject": "Laporan perkembangan yang diperbarui",
            "sop1b-legal_basis_html": '<ol><li onclick="bad()">Dasar diperbarui</li></ol><script>bad()</script>',
            "sop1b-facts_html": sop_draft.facts_html,
            "sop1b-legal_analysis_html": sop_draft.legal_analysis_html,
            "sop1b-conclusion_html": sop_draft.conclusion_html,
            "sop1b-closing": sop_draft.closing,
            "sop1b-prosecutor_name": prosecutor.display_name,
            "sop1b-prosecutor_rank": prosecutor.rank,
            "sop1b-prosecutor_nip": prosecutor.nip,
            "sop1b-kasi_opinion_html": "<p>Setuju diterbitkan.</p>",
            "sop1b-leader_instruction_html": "<p>Segera tindak lanjuti.</p>",
            "sop1b-barcode_image": SimpleUploadedFile(
                "barcode-sop1b.gif",
                b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
                content_type="image/gif",
            ),
        })

        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(reverse("cases:p17_draft_detail", args=[draft.pk]), payload)
            self.assertRedirects(response, reverse("cases:p17_draft_detail", args=[draft.pk]))
            sop_draft.refresh_from_db()
            self.assertTrue(sop_draft.barcode_image.name.startswith("sop-form-1b/barcodes/"))
            detail = self.client.get(reverse("cases:p17_draft_detail", args=[draft.pk]))
            self.assertContains(detail, 'alt="Barcode verifikasi SOP Form-1B"')

        self.assertEqual(sop_draft.subject, "Laporan perkembangan yang diperbarui")
        self.assertIn("Dasar diperbarui", sop_draft.legal_basis_html)
        self.assertNotIn("onclick", sop_draft.legal_basis_html)
        self.assertNotIn("script", sop_draft.legal_basis_html)
        self.assertEqual(sop_draft.last_edited_by, self.user)

    def test_p17_saves_multiple_structured_recipients(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p17-recipient", "kasi-p17-recipient@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        P16Draft.create_for_assignment(assignment, kasi)
        draft = P17Draft.create_for_spdp(spdp, self.user)
        recipients = [
            {"recipient": "Kepala Kepolisian Resor Buleleng", "place": "Singaraja"},
            {"recipient": "Kepala Kepolisian Sektor Sukasada", "place": "Singaraja"},
        ]

        response = self.client.post(
            reverse("cases:p17_draft_detail", args=[draft.pk]),
            self.p17_payload(draft, recipients_json=json.dumps(recipients)),
        )

        self.assertRedirects(response, reverse("cases:p17_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertIn("p17-recipient-numbered", draft.recipient_html)
        self.assertIn("Kepala Kepolisian Sektor Sukasada", draft.recipient_html)
        self.assertIn("Singaraja", draft.recipient_html)
        self.assertEqual(draft.recipient_html.count("Di -"), 1)

    def test_p17_layout_matches_reference_document_measurements(self):
        css = Path(settings.BASE_DIR, "static", "css", "p17-document.css").read_text(encoding="utf-8")
        self.assertIn("size: 8.5in 13in", css)
        self.assertIn("padding: 1cm 2.09cm 2cm 2cm", css)
        self.assertIn("font: 10pt/1.15 Arial", css)
        self.assertIn("min-height: 66pt", css)
        self.assertIn("font-size: 10pt", css)
        self.assertIn("border-top: 3pt double #111", css)
        self.assertIn("border-bottom: 0", css)
        self.assertIn("left: 76%", css)
        self.assertIn("margin-left: 0", css)
        self.assertIn("text-indent: 1.25cm", css)
        self.assertIn("line-height: 1.5", css)

    def test_p17_editor_saves_and_sanitizes_content(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p17-safe", "kasi-p17-safe@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        P16Draft.create_for_assignment(assignment, kasi)
        draft = P17Draft.create_for_spdp(spdp, self.user)
        payload = self.p17_payload(
            draft,
            letter_number="11",
            subject_html='<b onclick="alert(1)">Perihal P-17 teks biasa</b>',
            body_html='<p onclick="alert(1)">Isi P-17 diperbarui.</p><script>alert(2)</script>',
        )

        response = self.client.post(reverse("cases:p17_draft_detail", args=[draft.pk]), payload)

        self.assertRedirects(response, reverse("cases:p17_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertEqual(
            draft.letter_number,
            f"B-11/N.1.11/Um.1/{draft.letter_date.month:02d}/{draft.letter_date.year}",
        )
        self.assertIn("Isi P-17 diperbarui.", draft.body_html)
        self.assertNotIn("onclick", draft.body_html)
        self.assertNotIn("script", draft.body_html)
        self.assertEqual(draft.subject_html, "Perihal P-17 teks biasa")
        self.assertEqual(draft.last_edited_by, self.user)

    def test_p17_uploads_barcode_and_uses_automatic_pagination(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p17-barcode", "kasi-p17-barcode@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        P16Draft.create_for_assignment(assignment, kasi)
        draft = P17Draft.create_for_spdp(spdp, self.user)
        barcode = SimpleUploadedFile(
            "barcode-p17.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )
        response = self.client.post(
            reverse("cases:p17_draft_detail", args=[draft.pk]),
            self.p17_payload(draft, barcode_image=barcode),
        )
        self.assertRedirects(response, reverse("cases:p17_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertTrue(draft.barcode_image.name.startswith("p17/barcodes/"))

        javascript = Path(settings.BASE_DIR, "static", "js", "p17-editor.js").read_text(encoding="utf-8")
        self.assertIn("function paginate(content)", javascript)
        self.assertIn("splitBlockToFit", javascript)
        self.assertIn("createPaper(false", javascript)

    def test_p21_menu_and_list_are_available(self):
        response = self.client.get(reverse("cases:p21_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daftar P-21")
        self.assertContains(response, 'href="%s"' % reverse("cases:p21_list"))

    def test_create_and_edit_p21_from_spdp_with_p16(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p21", "kasi-p21@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        P16Draft.create_for_assignment(assignment, kasi)
        StageOne.objects.create(
            spdp=spdp,
            case_file_number="BP/P21/2026",
            cover_letter_number="B/P21/2026",
            laws_and_articles=spdp.laws_and_articles,
            cover_letter_document=SimpleUploadedFile(
                "pengantar-p21.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf",
            ),
            created_by=self.user,
        )

        response = self.client.post(reverse("cases:p21_create"), {"spdp": spdp.pk})
        draft = P21Draft.objects.get(spdp=spdp)
        self.assertRedirects(response, reverse("cases:p21_draft_detail", args=[draft.pk]))
        self.assertIn("Sudah Lengkap", draft.subject_html)
        self.assertIn("Hasil Penelitian Berkas Perkara", draft.legal_basis_html)
        self.assertIn("14 (empat belas) hari", draft.body_html)

        detail = self.client.get(reverse("cases:p21_draft_detail", args=[draft.pk]))
        self.assertContains(detail, "Identitas Surat")
        self.assertContains(detail, ">Dasar<")
        self.assertContains(detail, ">Isi<")
        self.assertContains(detail, "Tembusan")
        self.assertContains(detail, "data-p21-rich-editor=", count=3)
        self.assertContains(detail, "data-p21-subject=")
        self.assertContains(detail, 'inputmode="numeric"')
        self.assertContains(detail, "8,5 × 13 inci")
        self.assertContains(detail, "p16-standard-letterhead")
        self.assertContains(detail, "logo-kejaksaan-p16-transparent.png")
        self.assertContains(detail, 'enctype="multipart/form-data"')
        self.assertContains(detail, "verification-code-placeholder")
        self.assertContains(detail, "letter-recipient-rows")
        self.assertEqual(draft.copies_html.count("<li>"), 3)

        payload = self.p21_payload(
            draft,
            letter_number="4705",
            body_html='<p onclick="alert(1)">Isi P-21 aman.</p><script>alert(2)</script>',
        )
        saved = self.client.post(reverse("cases:p21_draft_detail", args=[draft.pk]), payload)
        self.assertRedirects(saved, reverse("cases:p21_draft_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertIn("Isi P-21 aman.", draft.body_html)
        self.assertNotIn("onclick", draft.body_html)
        self.assertNotIn("script", draft.body_html)
        self.assertEqual(
            draft.letter_number,
            f"B-4705/N.1.11/Um.1/{draft.letter_date.month:02d}/{draft.letter_date.year}",
        )
        self.assertEqual(draft.last_edited_by, self.user)

    def test_p21_only_allows_one_draft_per_spdp(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p21-once", "kasi-p21-once@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        P16Draft.create_for_assignment(assignment, kasi)
        StageOne.objects.create(
            spdp=spdp,
            case_file_number="BP/DOC/2026",
            cover_letter_number="B/DOC/2026",
            laws_and_articles=spdp.laws_and_articles,
            cover_letter_document=SimpleUploadedFile(
                "pengantar-doc.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf",
            ),
            created_by=self.user,
        )
        P21Draft.create_for_spdp(spdp, self.user)
        self.assertFalse(p21_accessible := self.client.get(reverse("cases:p21_list")).context["can_create"])
        self.assertIs(p21_accessible, False)

    def test_p21_generation_uses_configured_document_template(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-p21-template", "kasi-p21-template@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp, kasi_pidum=kasi, started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        P16Draft.create_for_assignment(assignment, kasi)
        DocumentTemplateConfiguration.objects.create(
            template_key="p21",
            sections={"body_html": "<p>Kalimat generate untuk {{ suspect_names }}.</p>"},
            updated_by=self.user,
        )

        draft = P21Draft.create_for_spdp(spdp, self.user)
        self.assertIn("Kalimat generate untuk Tersangka Satu.", draft.body_html)
        self.assertIn("Sudah Lengkap", draft.subject_html)

    def test_sop_form_02_and_03_follow_workflow_order(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-sop", "kasi-sop@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        P16Draft.create_for_assignment(assignment, kasi)
        P17Draft.create_for_spdp(spdp, self.user)

        list_02 = self.client.get(reverse("cases:sop_form_02_list"))
        self.assertEqual(list_02.status_code, 200)
        self.assertContains(list_02, "Daftar SOP Form 2")
        self.assertContains(list_02, "+ Buat SOP Form 2")
        response_02 = self.client.post(reverse("cases:sop_form_02_create"), {"spdp": spdp.pk})
        draft_02 = SOPForm02Draft.objects.get(spdp=spdp)
        self.assertRedirects(response_02, reverse("cases:sop_form_02_detail", args=[draft_02.pk]))
        self.assertIn("P-17", draft_02.body_html)

        detail_02 = self.client.get(reverse("cases:sop_form_02_detail", args=[draft_02.pk]))
        self.assertContains(detail_02, "Editor SOP Form 2")
        self.assertContains(detail_02, "data-sop-rich-editor=", count=2)
        self.assertContains(detail_02, "data-sop-subject=")
        self.assertContains(detail_02, "SOP FORM-2")
        self.assertContains(detail_02, "sop-form-02-layout.css")
        self.assertContains(detail_02, "sop-form-02-preview.js")
        self.assertContains(detail_02, "data-sop-sipede")
        self.assertContains(
            detail_02,
            reverse("cases:sop_form_02_sipede_upload", args=[draft_02.pk]),
        )
        self.assertContains(detail_02, "verification-code-placeholder")
        self.assertIn("A r s i p.", draft_02.copies_html)
        self.assertEqual(draft_02.copies_html.count("<li>"), 3)

        list_03 = self.client.get(reverse("cases:sop_form_03_list"))
        self.assertContains(list_03, "Daftar SOP Form 3")
        self.assertContains(list_03, "+ Buat SOP Form 3")
        response_03 = self.client.post(reverse("cases:sop_form_03_create"), {"spdp": spdp.pk})
        draft_03 = SOPForm03Draft.objects.get(spdp=spdp)
        self.assertRedirects(response_03, reverse("cases:sop_form_03_detail", args=[draft_03.pk]))
        self.assertIn(draft_02.letter_number, draft_03.body_html)
        self.assertIn(spdp.letter_number, draft_03.body_html)

        detail_03 = self.client.get(reverse("cases:sop_form_03_detail", args=[draft_03.pk]))
        self.assertContains(detail_03, "Editor SOP Form 3")
        self.assertContains(detail_03, "SOP FORM-03")
        self.assertContains(detail_03, "Demi Keadilan dan Kebenaran")
        self.assertContains(detail_03, "verification-code-placeholder")
        with patch("cases.sipede_p17.session_available", return_value=True) as session_available:
            response = self.client.post(
                reverse("cases:sop_form_03_sipede_upload", args=[draft_03.pk]),
                {"action": "session"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            session_available.call_args.kwargs,
            {
                "id_surat": settings.SIPEDE_SOP_FORM_03_ID,
                "document_label": "SOP Form 3",
                "form_route": "suratkeluar",
            },
        )

    def test_sop_form_content_is_sanitized(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-sop-safe", "kasi-sop-safe@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        P16Draft.create_for_assignment(assignment, kasi)
        P17Draft.create_for_spdp(spdp, self.user)
        draft = SOPForm02Draft.create_for_spdp(spdp, self.user)
        response = self.client.post(reverse("cases:sop_form_02_detail", args=[draft.pk]), self.sop_payload(draft, body_html='<p onclick="x()">Isi aman.</p><script>x()</script>'))
        self.assertRedirects(response, reverse("cases:sop_form_02_detail", args=[draft.pk]))
        draft.refresh_from_db()
        self.assertIn("Isi aman.", draft.body_html)
        self.assertNotIn("onclick", draft.body_html)
        self.assertNotIn("script", draft.body_html)

    def test_p18_p19_p20_and_sop_form_7_workflows(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user("kasi-doc-chain", "kasi-doc-chain@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(spdp=spdp, kasi_pidum=kasi, started_by=self.user, status=P16Assignment.Status.ASSIGNED)
        P16Draft.create_for_assignment(assignment, kasi)
        StageOne.objects.create(
            spdp=spdp,
            case_file_number="BP/DOC-CHAIN/2026",
            cover_letter_number="B/DOC-CHAIN/2026",
            laws_and_articles=spdp.laws_and_articles,
            cover_letter_document=SimpleUploadedFile(
                "pengantar-doc-chain.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf",
            ),
            created_by=self.user,
        )

        for name, label in (("p18_list", "Daftar P-18"), ("p19_list", "Daftar P-19")):
            page = self.client.get(reverse(f"cases:{name}"))
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, label)

        p18_response = self.client.post(reverse("cases:p18_create"), {"spdp": spdp.pk})
        p18 = CaseDocumentDraft.objects.get(spdp=spdp, document_type="p18")
        self.assertRedirects(p18_response, reverse("cases:p18_detail", args=[p18.pk]))
        self.assertIn("Berkas Perkara Asli", p18.body_html)
        p18_detail = self.client.get(reverse("cases:p18_detail", args=[p18.pk]))
        self.assertContains(p18_detail, "SURAT PENGANTAR")
        self.assertContains(p18_detail, "data-document-print")
        self.assertContains(p18_detail, "verification-code-placeholder")

        p19_response = self.client.post(reverse("cases:p19_create"), {"spdp": spdp.pk})
        p19 = CaseDocumentDraft.objects.get(spdp=spdp, document_type="p19")
        self.assertRedirects(p19_response, reverse("cases:p19_detail", args=[p19.pk]))
        self.assertEqual(p19.legal_basis_html, "")
        self.assertEqual(p19.body_html, "")
        p19_detail = self.client.get(reverse("cases:p19_detail", args=[p19.pk]))
        self.assertContains(p19_detail, "Editor P-19")
        self.assertContains(p19_detail, "p19-editor.css")
        self.assertContains(p19_detail, 'data-document-type="p19"')
        self.assertContains(p19_detail, "data-document-subject=")
        self.assertContains(p19_detail, 'inputmode="numeric"')
        self.assertContains(p19_detail, "verification-code-placeholder")
        p19_save = self.client.post(
            reverse("cases:p19_detail", args=[p19.pk]),
            self.case_document_payload(
                p19,
                letter_number="4704",
                body_html="<p>Isi P-19 ditulis manual.</p>",
            ),
        )
        self.assertRedirects(p19_save, reverse("cases:p19_detail", args=[p19.pk]))
        p19.refresh_from_db()
        self.assertEqual(
            p19.letter_number,
            f"B-4704/N.1.11/Um.1/{p19.letter_date.month:02d}/{p19.letter_date.year}",
        )

        p20_page = self.client.get(reverse("cases:p20_list"))
        self.assertContains(p20_page, "+ Buat P-20")
        p20_response = self.client.post(reverse("cases:p20_create"), {"spdp": spdp.pk})
        p20 = CaseDocumentDraft.objects.get(spdp=spdp, document_type="p20")
        self.assertRedirects(p20_response, reverse("cases:p20_detail", args=[p20.pk]))
        self.assertIn(p18.letter_number, p20.legal_basis_html)
        p20_detail = self.client.get(reverse("cases:p20_detail", args=[p20.pk]))
        self.assertContains(p20_detail, "data-document-print")
        self.assertContains(p20_detail, "verification-code-placeholder")

        p21 = P21Draft.create_for_spdp(spdp, self.user)
        sop7_page = self.client.get(reverse("cases:sop_form_07_list"))
        self.assertContains(sop7_page, "+ Buat SOP Form 7")
        sop7_response = self.client.post(reverse("cases:sop_form_07_create"), {"spdp": spdp.pk})
        sop7 = CaseDocumentDraft.objects.get(spdp=spdp, document_type="sop07")
        self.assertRedirects(sop7_response, reverse("cases:sop_form_07_detail", args=[sop7.pk]))
        self.assertIn(p21.letter_number, sop7.legal_basis_html)
        detail = self.client.get(reverse("cases:sop_form_07_detail", args=[sop7.pk]))
        self.assertContains(detail, "8,5 × 14 inci")
        self.assertContains(detail, "SOP FORM-7")
        self.assertContains(detail, 'inputmode="numeric"')
        self.assertContains(detail, "sop07-editor.css")
        self.assertContains(detail, "data-sop07-recipient")
        self.assertContains(detail, "data-document-print")
        self.assertContains(detail, "verification-code-placeholder")
        self.assertIn('<ol start="2">', sop7.body_html)
        self.assertEqual(sop7.copies_html.count("<li>"), 3)
        sop7_save = self.client.post(
            reverse("cases:sop_form_07_detail", args=[sop7.pk]),
            self.case_document_payload(sop7, letter_number="4706"),
        )
        self.assertRedirects(sop7_save, reverse("cases:sop_form_07_detail", args=[sop7.pk]))
        sop7.refresh_from_db()
        self.assertEqual(
            sop7.letter_number,
            f"B-4706/N.1.11/Um.1/{sop7.letter_date.month:02d}/{sop7.letter_date.year}",
        )
        self.assertEqual(settings.SIPEDE_P18_ID, "8")
        sipede_documents = (
            ("p18_sipede_upload", p18, "P-18", settings.SIPEDE_P18_ID, "administrasiperkara"),
            ("p19_sipede_upload", p19, "P-19", settings.SIPEDE_P19_ID, "suratkeluar"),
            ("p20_sipede_upload", p20, "P-20", settings.SIPEDE_P20_ID, "suratkeluar"),
            ("sop_form_07_sipede_upload", sop7, "SOP Form 7", settings.SIPEDE_SOP_FORM_07_ID, "suratkeluar"),
        )
        with patch("cases.sipede_p17.session_available", return_value=True) as session_available:
            responses = [
                self.client.post(reverse(f"cases:{url_name}", args=[draft.pk]), {"action": "session"})
                for url_name, draft, _label, _id_surat, _form_route in sipede_documents
            ]
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(
            [call.kwargs for call in session_available.call_args_list],
            [
                {
                    "id_surat": id_surat,
                    "document_label": label,
                    "form_route": form_route,
                }
                for _url_name, _draft, label, id_surat, form_route in sipede_documents
            ],
        )

    def test_new_document_menus_are_in_sidebar(self):
        response = self.client.get(reverse("cases:p18_list"))
        for label in ("P-18", "P-19", "P-20", "SOP Form 7", "SOP Form 2", "SOP Form 3", "Tahap 1"):
            self.assertContains(response, label)
        for hidden_label in ("BA Koordinasi I", "BA Koordinasi II", "BA Koordinasi III"):
            self.assertNotContains(response, hidden_label)

    def test_remaining_days_column_is_shown_on_workflow_lists_except_exclusions(self):
        included_lists = (
            "p16_list",
            "p17_list",
            "stage_one_list",
            "sop_form_02_list",
            "p19_list",
            "p21_list",
        )
        for url_name in included_lists:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(f"cases:{url_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Sisa Hari")

        excluded_lists = ("p18_list", "p20_list", "sop_form_03_list", "sop_form_07_list")
        for url_name in excluded_lists:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(f"cases:{url_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Sisa Hari")

        for url_name in ("p18_list", "p20_list", "sop_form_03_list", "sop_form_07_list"):
            with self.subTest(stats_only=url_name):
                response = self.client.get(reverse(f"cases:{url_name}"))
                self.assertContains(response, 'class="case-stat-grid"')
                self.assertNotContains(response, "Harus Diselesaikan")

    def test_p16_list_uses_current_workflow_remaining_days(self):
        spdp = self.create_spdp()
        kasi = User.objects.create_user(
            "kasi-deadline-list", "kasi-deadline-list@test.id", "rahasia-kuat",
        )
        kasi.roles.add(self.kasi_role)
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=self.user,
            status=P16Assignment.Status.ASSIGNED,
        )
        draft, _ = P16Draft.create_for_assignment(assignment, kasi)
        draft.draft_number = "PRINT-100/N.1.11/Um.1/11/2026"
        draft.letter_date = timezone.localdate() - timedelta(days=4)
        draft.save(update_fields=("draft_number", "letter_date"))

        response = self.client.get(reverse("cases:p16_list"))
        self.assertContains(response, "Sisa Hari")
        self.assertContains(response, "Sisa 26 hari")
        self.assertContains(response, 'deadline-badge safe')
        self.assertContains(response, "Harus Diselesaikan")
        self.assertContains(response, "Notif")
        self.assertContains(response, "case-priority-quick-actions")
        self.assertContains(response, "workflow-row-actions")
        self.assertContains(
            response,
            reverse("dashboard:send_reminder", args=[spdp.pk]),
        )

        p17_before_issue = self.client.get(reverse("cases:p17_list"))
        self.assertContains(p17_before_issue, "Tidak ada aktivitas mendesak")
        p17 = P17Draft.create_for_spdp(spdp, self.user)
        p17.letter_number = "B-17/N.1.11/Um.1/11/2026"
        p17.letter_date = timezone.localdate()
        p17.save(update_fields=("letter_number", "letter_date", "updated_at"))
        self.assertContains(self.client.get(reverse("cases:p16_list")), "Tidak ada aktivitas mendesak")
        p17_activity = self.client.get(reverse("cases:p17_list"))
        self.assertContains(p17_activity, "Sisa 30 hari")
        self.assertContains(p17_activity, "Notif")

        activity_css = Path(
            settings.BASE_DIR, "static", "css", "cases.css",
        ).read_text(encoding="utf-8")
        self.assertIn(".case-priority-list{max-height:220px", activity_css)
        self.assertIn("overflow-y:auto", activity_css)

    def test_issued_p16_p17_and_sop2_actions_are_exclusive(self):
        spdp, _ = self.create_issued_p16_case("FLOW-A")

        p16_page = self.client.get(reverse("cases:p16_list"))
        self.assertContains(p16_page, "workflow-row-actions")
        self.assertContains(p16_page, "action-menu.js")
        self.assertContains(p16_page, "Generate Tahap 1")
        self.assertContains(p16_page, "Generate P-17")
        action_menu_script = Path(
            settings.BASE_DIR, "static", "js", "action-menu.js",
        ).read_text(encoding="utf-8")
        self.assertIn("list.style.position = 'fixed'", action_menu_script)
        self.assertIn("const openAbove", action_menu_script)
        self.assertIn("list.style.zIndex = '10000'", action_menu_script)

        response = self.client.post(reverse(
            "cases:workflow_generate", args=["p16", "p17", spdp.pk],
        ))
        p17 = P17Draft.objects.get(spdp=spdp)
        self.assertRedirects(response, reverse("cases:p17_draft_detail", args=[p17.pk]))
        locked_p16 = self.client.get(reverse("cases:p16_list"))
        self.assertContains(locked_p16, "Tahap lanjutan sudah dibuat")
        self.assertNotContains(locked_p16, "Generate Tahap 1")

        p17.letter_number = "B-17/N.1.11/Um.1/11/2026"
        p17.save(update_fields=("letter_number", "updated_at"))
        p17_page = self.client.get(reverse("cases:p17_list"))
        self.assertContains(p17_page, "Generate Tahap 1")
        self.assertContains(p17_page, "Generate SOP Form 2")

        response = self.client.post(reverse(
            "cases:workflow_generate", args=["p17", "sop02", spdp.pk],
        ))
        sop02 = SOPForm02Draft.objects.get(spdp=spdp)
        self.assertRedirects(response, reverse("cases:sop_form_02_detail", args=[sop02.pk]))
        locked_p17 = self.client.get(reverse("cases:p17_list"))
        self.assertContains(locked_p17, "Tahap lanjutan sudah dibuat")
        self.assertNotContains(locked_p17, "Generate SOP Form 2")

        sop02.letter_number = "B-02/N.1.11/Um.1/11/2026"
        sop02.save(update_fields=("letter_number", "updated_at"))
        sop02_page = self.client.get(reverse("cases:sop_form_02_list"))
        self.assertContains(sop02_page, "Generate Tahap 1")
        self.assertContains(sop02_page, "Generate SOP Form 3")

    def test_stage_one_p18_p19_and_p20_actions_are_exclusive(self):
        spdp, _ = self.create_issued_p16_case("FLOW-B")
        self.create_stage_one_record(spdp, "FLOW-B")

        stage_page = self.client.get(reverse("cases:stage_one_list"))
        self.assertContains(stage_page, "Generate P-21")
        self.assertContains(stage_page, "Generate P-18")
        response = self.client.post(reverse(
            "cases:workflow_generate", args=["stage1", "p18", spdp.pk],
        ))
        p18 = CaseDocumentDraft.objects.get(spdp=spdp, document_type="p18")
        self.assertRedirects(response, reverse("cases:p18_detail", args=[p18.pk]))
        locked_stage = self.client.get(reverse("cases:stage_one_list"))
        self.assertContains(locked_stage, "Tahap lanjutan sudah dibuat")
        self.assertNotContains(locked_stage, "Generate P-21")

        p18.letter_number = "B-18/N.1.11/Um.1/11/2026"
        p18.save(update_fields=("letter_number", "updated_at"))
        self.assertContains(self.client.get(reverse("cases:p18_list")), "Generate P-19")
        self.client.post(reverse("cases:workflow_generate", args=["p18", "p19", spdp.pk]))
        p19 = CaseDocumentDraft.objects.get(spdp=spdp, document_type="p19")
        p19.letter_number = "B-19/N.1.11/Um.1/11/2026"
        p19.save(update_fields=("letter_number", "updated_at"))
        p19_page = self.client.get(reverse("cases:p19_list"))
        self.assertContains(p19_page, "Generate P-21")
        self.assertContains(p19_page, "Generate P-20")

        self.client.post(reverse("cases:workflow_generate", args=["p19", "p20", spdp.pk]))
        self.assertTrue(CaseDocumentDraft.objects.filter(spdp=spdp, document_type="p20").exists())
        locked_p19 = self.client.get(reverse("cases:p19_list"))
        self.assertContains(locked_p19, "Tahap lanjutan sudah dibuat")
        self.assertNotContains(locked_p19, "Generate P-21")

    def test_stage_one_p21_and_sop7_actions_are_exclusive(self):
        spdp, _ = self.create_issued_p16_case("FLOW-C")
        self.create_stage_one_record(spdp, "FLOW-C")
        response = self.client.post(reverse(
            "cases:workflow_generate", args=["stage1", "p21", spdp.pk],
        ))
        p21 = P21Draft.objects.get(spdp=spdp)
        self.assertRedirects(response, reverse("cases:p21_draft_detail", args=[p21.pk]))
        self.assertFalse(CaseDocumentDraft.objects.filter(spdp=spdp, document_type="p18").exists())

        p21.letter_number = "B-21/N.1.11/Um.1/11/2026"
        p21.save(update_fields=("letter_number", "updated_at"))
        p21_page = self.client.get(reverse("cases:p21_list"))
        self.assertContains(p21_page, "Generate SOP Form 7")
        self.client.post(reverse(
            "cases:workflow_generate", args=["p21", "sop07", spdp.pk],
        ))
        self.assertTrue(CaseDocumentDraft.objects.filter(spdp=spdp, document_type="sop07").exists())
        locked_p21 = self.client.get(reverse("cases:p21_list"))
        self.assertContains(locked_p21, "Tahap lanjutan sudah dibuat")
        self.assertNotContains(locked_p21, "Generate SOP Form 7")

    def test_create_all_coordination_minutes_from_p16(self):
        spdp, kasi, prosecutor, p16 = self.create_coordination_prerequisites()

        for number, coordination_type in enumerate(("ba1", "ba2", "ba3"), start=1):
            response = self.client.post(reverse(f"cases:coordination_{number}_create"), {"spdp": spdp.pk})
            draft = CoordinationMinutesDraft.objects.get(spdp=spdp, coordination_type=coordination_type)
            self.assertRedirects(response, reverse(f"cases:coordination_{number}_detail", args=[draft.pk]))
            self.assertEqual(draft.prosecutor_name, prosecutor.display_name)
            self.assertEqual(draft.prosecutor_supervisor_name, kasi.display_name)
            self.assertIn(p16.draft_number, draft.body_html)
            self.assertIn(spdp.letter_number, draft.body_html)
            detail = self.client.get(reverse(f"cases:coordination_{number}_detail", args=[draft.pk]))
            expected_title = {1: "BERITA ACARA KOORDINASI I", 2: "BERITA ACARA KOORDINASI KE-II", 3: "BERITA ACARA KOORDINASI KE-III"}[number]
            self.assertContains(detail, expected_title)

    def test_coordination_editor_matches_reference_structure(self):
        spdp, _, _, _ = self.create_coordination_prerequisites()
        draft = CoordinationMinutesDraft.create_for_spdp(spdp, "ba1", self.user)

        response = self.client.get(reverse("cases:coordination_1_detail", args=[draft.pk]))

        self.assertEqual(response.status_code, 200)
        for label in ("Identitas Koordinasi", "Penuntut Umum", "Penyidik", "Materi Koordinasi", "Pejabat yang Mengetahui", "Dokumentasi"):
            self.assertContains(response, label)
        self.assertContains(response, "BERITA ACARA KOORDINASI I")
        self.assertContains(response, "ANTARA PENYIDIK DAN PENUNTUT UMUM")
        self.assertContains(response, "SOP FORM-6")
        self.assertContains(response, "Legal · 8,5 × 14 inci")
        self.assertContains(response, "vendor/jodit/jodit.min.js")
        self.assertContains(response, "data-coordination-pages")
        self.assertContains(response, "data-coordination-image=", count=3)

    def test_coordination_editor_saves_and_sanitizes_body(self):
        spdp, _, _, _ = self.create_coordination_prerequisites()
        draft = CoordinationMinutesDraft.create_for_spdp(spdp, "ba2", self.user)

        detail = self.client.get(reverse("cases:coordination_2_detail", args=[draft.pk]))
        self.assertContains(detail, "data-coordination-print")
        self.assertContains(detail, "data-coordination-barcode-input")
        self.assertContains(detail, "verification-code-placeholder")

        payload = self.coordination_payload(
            draft,
            investigator_name="IPDA I Ketut Penyidik",
            investigator_rank="IPDA",
            investigator_nrp="90112233",
            investigator_position="Penyidik Pembantu",
            body_html='<p onclick="alert(1)">Materi koordinasi diperbarui.</p><script>alert(2)</script>',
            barcode_image=SimpleUploadedFile(
                "barcode-koordinasi.gif",
                b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
                content_type="image/gif",
            ),
        )
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(reverse("cases:coordination_2_detail", args=[draft.pk]), payload)
            self.assertRedirects(response, reverse("cases:coordination_2_detail", args=[draft.pk]))
            draft.refresh_from_db()
            self.assertTrue(draft.barcode_image.name.startswith("coordination/barcodes/"))
            saved_detail = self.client.get(reverse("cases:coordination_2_detail", args=[draft.pk]))
            self.assertContains(saved_detail, 'alt="Barcode verifikasi koordinasi"')

        self.assertEqual(draft.investigator_name, "IPDA I Ketut Penyidik")
        self.assertIn("Materi koordinasi diperbarui.", draft.body_html)
        self.assertNotIn("onclick", draft.body_html)
        self.assertNotIn("script", draft.body_html)
        self.assertEqual(draft.last_edited_by, self.user)

    def test_coordination_layout_uses_legal_and_f4_pages_with_automatic_pagination(self):
        css = Path(settings.BASE_DIR, "static", "css", "coordination-document.css").read_text(encoding="utf-8")
        javascript = Path(settings.BASE_DIR, "static", "js", "coordination-editor.js").read_text(encoding="utf-8")
        self.assertIn("size:8.5in 14in", css)
        detail_template = Path(settings.BASE_DIR, "templates", "cases", "coordination_detail.html").read_text(encoding="utf-8")
        self.assertIn("size:8.5in 13in", detail_template)
        self.assertIn("padding:1in .75in", css)
        self.assertIn("font:11pt/1.15 Arial", css)
        self.assertIn("function paginate(fragment)", javascript)
        self.assertIn("splitBlockToFit", javascript)
        self.assertIn("coordination-documentation:not(.is-empty)", javascript)

    def test_populate_case_data_covers_scenarios_and_is_idempotent(self):
        kasi = User.objects.create_user("seed-kasi", "seed-kasi@test.id", "rahasia-kuat")
        kasi.roles.add(self.kasi_role)
        prosecutor = User.objects.create_user("seed-jaksa", "seed-jaksa@test.id", "rahasia-kuat")
        prosecutor.roles.add(self.prosecutor_role)
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)

        with override_settings(MEDIA_ROOT=media.name):
            output = io.StringIO()
            call_command("populate_case_data", stdout=output)
            self.assertIn("50 perkara berhasil ditambahkan.", output.getvalue())

            self.assertEqual(SPDP.objects.filter(letter_number__startswith="B/9").count(), 50)
            self.assertEqual(
                set(SPDP.objects.values_list("status", flat=True)),
                set(SPDP.Status.values),
            )
            self.assertEqual(
                set(SPDP.objects.values_list("legal_subject", flat=True)),
                set(SPDP.LegalSubject.values),
            )
            self.assertEqual(set(Suspect.objects.values_list("suspect_type", flat=True)), set(Suspect.SuspectType.values))
            self.assertEqual(set(Receipt.objects.values_list("receipt_type", flat=True)), set(Receipt.ReceiptType.values))
            self.assertEqual(set(CaseDocumentDraft.objects.values_list("document_type", flat=True)), set(CaseDocumentDraft.DocumentType.values))
            self.assertTrue(StageOne.objects.exists())
            self.assertTrue(P16Assignment.objects.exists())
            self.assertTrue(P16Draft.objects.exists())
            self.assertFalse(
                P16Assignment.objects.filter(status=P16Assignment.Status.ASSIGNED)
                .exclude(draft__isnull=False)
                .exists()
            )
            self.assertFalse(
                SPDP.objects.filter(p16_assignment__isnull=False)
                .exclude(status=SPDP.Status.PROCESS)
                .exists()
            )
            self.assertFalse(
                StageOne.objects.exclude(spdp__p16_assignment__status=P16Assignment.Status.ASSIGNED).exists()
            )
            self.assertTrue(P17Draft.objects.exists())
            self.assertTrue(P21Draft.objects.exists())
            self.assertTrue(SOPForm02Draft.objects.exists())
            self.assertTrue(SOPForm03Draft.objects.exists())
            self.assertTrue(SOPForm1BDraft.objects.exists())
            self.assertEqual(
                set(CoordinationMinutesDraft.objects.values_list("coordination_type", flat=True)),
                set(CoordinationMinutesDraft.CoordinationType.values),
            )

            output = io.StringIO()
            call_command("populate_case_data", stdout=output)
            self.assertIn("50 perkara pada rangkaian ini sudah tersedia.", output.getvalue())
            self.assertEqual(SPDP.objects.filter(letter_number__startswith="B/9").count(), 50)
