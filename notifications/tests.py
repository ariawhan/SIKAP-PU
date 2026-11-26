import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from cases.models import CaseDocumentDraft, CaseInvestigator, P16Assignment, P16Draft, P21Draft, SOPForm03Draft, SPDP, StageOne, Suspect
from cases.reminders import case_deadline_for_spdp
from .models import CaseReminderDispatch, DocumentIssuedDispatch, NotificationLog, NotificationMenuSetting, NotificationSetting, NotificationTemplate, WebNotification
from .services import (
    build_p16_assignment_messages,
    case_detail_template_context,
    process_due_case_deadline_reminders,
    process_notification_queue,
    render_notification_template,
    send_case_deadline_reminder,
    send_document_issued_notifications,
    send_sop_form_03_issued_notifications,
)
from .template_defaults import DEADLINE_TEMPLATE_STAGES, DOCUMENT_ISSUED_STAGES, TEMPLATE_DEFINITIONS, issued_template_key


def mock_json_response(payload, status=200):
    context = MagicMock()
    context.read.return_value = json.dumps(payload).encode("utf-8")
    context.status = status
    response = MagicMock()
    response.__enter__.return_value = context
    return response


class CaseDeadlineReminderTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.kasi_role = Role.objects.get(code=Role.KASI_PIDUM)
        self.prosecutor_role = Role.objects.get(code=Role.PROSECUTOR)
        self.employee_role = Role.objects.get(code=Role.EMPLOYEE)
        self.kasubsi_role = Role.objects.get(code=Role.KASUBSI_PREPROSECUTION)
        self.actor = User.objects.create_user("reminder-actor", "reminder-actor@test.id", "rahasia-kuat")
        self.kasi = User.objects.create_user("reminder-kasi", "reminder-kasi@test.id", "rahasia-kuat")
        self.prosecutor = User.objects.create_user("reminder-jaksa", "reminder-jaksa@test.id", "rahasia-kuat")
        self.staff = User.objects.create_user("reminder-staff", "reminder-staff@test.id", "rahasia-kuat")
        self.kasubsi = User.objects.create_user("reminder-kasubsi", "reminder-kasubsi@test.id", "rahasia-kuat")
        self.kasi.roles.add(self.kasi_role)
        self.prosecutor.roles.add(self.prosecutor_role)
        self.staff.roles.add(self.employee_role)
        self.kasubsi.roles.add(self.kasubsi_role)
        self.spdp = SPDP.objects.create(
            directorate="Direktorat Umum",
            investigator_agency="Kepolisian RI",
            investigating_unit="Satreskrim Polres Buleleng",
            investigation_order_number="SP.Sidik/1/X/2026",
            investigation_order_date=self.today - timedelta(days=40),
            letter_number="B/SPDP/REMINDER/2026",
            letter_date=self.today - timedelta(days=39),
            received_date=self.today - timedelta(days=38),
            case_type="Pencurian",
            case_summary="Perkara reminder.",
            laws_and_articles="Pasal 362 KUHP",
            created_by=self.actor,
        )
        self.assignment = P16Assignment.objects.create(
            spdp=self.spdp,
            kasi_pidum=self.kasi,
            started_by=self.actor,
            status=P16Assignment.Status.ASSIGNED,
        )
        self.assignment.prosecutors.add(self.prosecutor)
        self.assignment.administrative_staff.add(self.staff)
        self.draft, _ = P16Draft.create_for_assignment(self.assignment, self.kasi)
        self.draft.draft_number = "PRINT-REMINDER/N.1.11/Um.1/10/2026"
        self.draft.letter_date = self.today - timedelta(days=28)
        self.draft.save(update_fields=("draft_number", "letter_date", "updated_at"))

    def test_case_messages_list_all_suspects_prosecutors_and_staff(self):
        self.prosecutor.first_name = "I Made"
        self.prosecutor.last_name = "Jaksa Pertama"
        self.prosecutor.save(update_fields=("first_name", "last_name"))
        self.staff.first_name = "Ni Luh"
        self.staff.last_name = "Petugas Pertama"
        self.staff.save(update_fields=("first_name", "last_name"))
        second_prosecutor = User.objects.create_user(
            "reminder-jaksa-2", "reminder-jaksa-2@test.id", "rahasia-kuat",
            first_name="Komang", last_name="Jaksa Kedua",
        )
        second_staff = User.objects.create_user(
            "reminder-staff-2", "reminder-staff-2@test.id", "rahasia-kuat",
            first_name="Kadek", last_name="Petugas Kedua",
        )
        self.assignment.prosecutors.add(second_prosecutor)
        self.assignment.appointed_prosecutors.add(self.prosecutor, second_prosecutor)
        self.assignment.administrative_staff.add(second_staff)
        Suspect.objects.create(
            spdp=self.spdp, sequence=1, name="I Made Pelaku",
            suspect_type=Suspect.SuspectType.SUSPECT,
        )
        Suspect.objects.create(
            spdp=self.spdp, sequence=2, name="Komang Terlapor", alias="Komang",
            suspect_type=Suspect.SuspectType.REPORTED,
        )

        details = case_detail_template_context(self.spdp, self.assignment)
        self.assertEqual(
            details["daftar_pelaku"],
            "1. I Made Pelaku (Tersangka); 2. Komang Terlapor alias Komang (Terlapor)",
        )
        self.assertEqual(
            details["daftar_jaksa"],
            "1. I Made Jaksa Pertama; 2. Komang Jaksa Kedua",
        )
        self.assertEqual(
            details["daftar_pegawai"],
            "1. Ni Luh Petugas Pertama; 2. Kadek Petugas Kedua",
        )

        assignment_message = build_p16_assignment_messages(self.assignment)["whatsapp"]
        for expected in (
            "I Made Pelaku", "Komang Terlapor", "I Made Jaksa Pertama",
            "Komang Jaksa Kedua", "Ni Luh Petugas Pertama", "Kadek Petugas Kedua",
        ):
            self.assertIn(expected, assignment_message)

        deadline = case_deadline_for_spdp(self.spdp, self.today)
        send_case_deadline_reminder(deadline, self.actor)
        web_message = WebNotification.objects.filter(spdp=self.spdp).first().message
        self.assertIn("Komang Terlapor", web_message)
        self.assertIn("Komang Jaksa Kedua", web_message)
        self.assertIn("Kadek Petugas Kedua", web_message)

    def test_case_detail_uses_reported_fallback_before_names_are_available(self):
        empty_spdp = SPDP.objects.create(
            directorate="Direktorat Umum",
            investigator_agency="Kepolisian RI",
            investigating_unit="Satreskrim Polres Buleleng",
            investigation_order_number="SP.Sidik/KOSONG/XI/2026",
            investigation_order_date=self.today,
            letter_number="B/SPDP/KOSONG/2026",
            letter_date=self.today,
            received_date=self.today,
            case_type="Penyelidikan",
            case_summary="Pelaku masih terlapor.",
            laws_and_articles="Dalam penyelidikan",
            created_by=self.actor,
        )
        details = case_detail_template_context(empty_spdp)
        self.assertEqual(details["daftar_pelaku"], "Masih terlapor (nama belum tersedia)")
        self.assertEqual(details["daftar_jaksa"], "Belum ada Jaksa yang ditunjuk")
        self.assertEqual(
            details["daftar_pegawai"], "Belum ada petugas administrasi yang ditunjuk",
        )

    def test_deadline_colors_follow_day_28_29_and_30_rules(self):
        deadline = case_deadline_for_spdp(self.spdp, self.today)
        self.assertEqual(deadline.color_class, "warning")
        self.assertEqual(deadline.elapsed_days, 28)

        self.draft.letter_date = self.today - timedelta(days=10)
        self.draft.save(update_fields=("letter_date", "updated_at"))
        self.spdp.p16_assignment.draft = self.draft
        self.assertEqual(case_deadline_for_spdp(self.spdp, self.today).color_class, "safe")

        self.draft.letter_date = self.today - timedelta(days=31)
        self.draft.save(update_fields=("letter_date", "updated_at"))
        self.spdp.p16_assignment.draft = self.draft
        overdue = case_deadline_for_spdp(self.spdp, self.today)
        self.assertEqual(overdue.color_class, "overdue")
        self.assertEqual(overdue.remaining_days, -1)

    def test_automatic_reminder_targets_all_assigned_roles_once(self):
        NotificationSetting.objects.update_or_create(pk=1, defaults={"automatic_notification_enabled": True})
        processed = process_due_case_deadline_reminders(self.today)
        self.assertEqual(processed, 1)
        self.assertEqual(WebNotification.objects.filter(spdp=self.spdp).count(), 4)
        self.assertEqual(
            set(WebNotification.objects.filter(spdp=self.spdp).values_list("recipient_id", flat=True)),
            {self.kasi.pk, self.prosecutor.pk, self.staff.pk, self.kasubsi.pk},
        )
        self.assertEqual(CaseReminderDispatch.objects.filter(spdp=self.spdp).count(), 1)
        self.assertEqual(process_due_case_deadline_reminders(self.today), 0)
        self.assertEqual(WebNotification.objects.filter(spdp=self.spdp).count(), 4)

    def test_sop_form_03_issued_notification_queues_whatsapp_and_telegram_for_case_team(self):
        users = (self.kasi, self.prosecutor, self.staff, self.kasubsi)
        for index, user in enumerate(users, start=1):
            user.whatsapp_number = f"0812345678{index:02d}"
            user.telegram_chat_id = str(9000 + index)
            user.save(update_fields=("whatsapp_number", "telegram_chat_id"))
        draft = SOPForm03Draft.create_for_spdp(self.spdp, self.actor)
        draft.letter_number = "B-300/N.1.11/Um.1/11/2026"
        draft.save(update_fields=("letter_number", "updated_at"))
        NotificationSetting.objects.update_or_create(
            pk=1, defaults={"whatsapp_enabled": True, "telegram_enabled": True},
        )
        NotificationMenuSetting.objects.update_or_create(
            menu_key=NotificationMenuSetting.Menu.SOP_FORM_03,
            defaults={"whatsapp_enabled": True, "telegram_enabled": True},
        )

        send_sop_form_03_issued_notifications(draft.pk, self.actor.pk)

        logs = NotificationLog.objects.filter(context_label__startswith="SOP Form 3")
        self.assertEqual(logs.count(), 8)
        self.assertEqual(
            set(logs.values_list("channel", flat=True)),
            {NotificationLog.Channel.WHATSAPP, NotificationLog.Channel.TELEGRAM},
        )
        self.assertEqual(
            set(logs.values_list("status", flat=True)),
            {NotificationLog.Status.QUEUED},
        )
        self.assertTrue(all(
            "SOP FORM 3 TERBIT" in message and draft.letter_number in message
            for message in logs.values_list("message", flat=True)
        ))
        self.assertEqual(
            set(WebNotification.objects.filter(
                spdp=self.spdp, kind=WebNotification.Kind.DOCUMENT_ISSUED,
            ).values_list("recipient_id", flat=True)),
            {self.kasi.pk, self.prosecutor.pk, self.staff.pk, self.kasubsi.pk},
        )
        self.assertEqual(
            DocumentIssuedDispatch.objects.get(
                stage_key="sop03", document_id=draft.pk,
            ).recipient_count,
            4,
        )

        # Simpan lalu upload dapat memanggil layanan yang sama, tetapi tidak boleh menggandakan pesan.
        send_sop_form_03_issued_notifications(draft.pk, self.actor.pk)
        self.assertEqual(logs.count(), 8)

    def test_p16_issued_notification_is_queued_for_every_investigator(self):
        self.prosecutor.first_name = "I Made"
        self.prosecutor.last_name = "Jaksa Penuntut"
        self.prosecutor.save(update_fields=("first_name", "last_name"))
        Suspect.objects.create(
            spdp=self.spdp, sequence=1, name="Komang Terlapor",
            suspect_type=Suspect.SuspectType.REPORTED,
        )
        CaseInvestigator.objects.create(
            spdp=self.spdp, sequence=1, name="IPDA I Nyoman Penyidik",
            phone="081234567890",
        )
        CaseInvestigator.objects.create(
            spdp=self.spdp, sequence=2, name="AIPDA Kadek Penyidik",
            phone="081398765432",
        )
        NotificationSetting.objects.update_or_create(
            pk=1, defaults={"whatsapp_enabled": True, "telegram_enabled": False},
        )
        NotificationMenuSetting.objects.update_or_create(
            menu_key=NotificationMenuSetting.Menu.P16,
            defaults={"whatsapp_enabled": True},
        )

        recipient_count = send_document_issued_notifications(
            spdp_id=self.spdp.pk,
            stage_key=NotificationMenuSetting.Menu.P16,
            document_id=self.draft.pk,
            document_number=self.draft.draft_number,
            document_date=self.draft.letter_date,
            actor_id=self.actor.pk,
        )

        investigator_logs = NotificationLog.objects.filter(
            context_label__startswith="P-16 Terbit untuk Penyidik",
        ).order_by("pk")
        self.assertEqual(investigator_logs.count(), 2)
        self.assertEqual(
            set(investigator_logs.values_list("recipient", flat=True)),
            {"6281234567890", "6281398765432"},
        )
        self.assertEqual(
            set(investigator_logs.values_list("recipient_name", flat=True)),
            {"IPDA I Nyoman Penyidik", "AIPDA Kadek Penyidik"},
        )
        self.assertTrue(all(
            "Komang Terlapor" in message and "I Made Jaksa Penuntut" in message
            for message in investigator_logs.values_list("message", flat=True)
        ))
        self.assertTrue(all(
            item.status == NotificationLog.Status.QUEUED for item in investigator_logs
        ))
        self.assertEqual(recipient_count, 6)
        self.assertEqual(
            DocumentIssuedDispatch.objects.get(stage_key="p16", document_id=self.draft.pk).recipient_count,
            6,
        )

    def test_spdp_reminder_starts_at_h_minus_two_before_p16_is_issued(self):
        spdp = SPDP.objects.create(
            directorate="Direktorat Umum",
            investigator_agency="Kepolisian RI",
            investigating_unit="Satreskrim Polres Buleleng",
            investigation_order_number="SP.Sidik/H-2/XI/2026",
            investigation_order_date=self.today - timedelta(days=2),
            letter_number="B/SPDP/H-2/2026",
            letter_date=self.today - timedelta(days=1),
            received_date=self.today,
            case_type="Pencurian",
            case_summary="Perkara menunggu penerbitan P-16.",
            laws_and_articles="Pasal 362 KUHP",
            created_by=self.actor,
        )

        deadline = case_deadline_for_spdp(spdp, self.today)

        self.assertEqual(deadline.stage_key, "spdp")
        self.assertEqual(deadline.stage_label, "Penerbitan P-16")
        self.assertEqual(deadline.period_days, 2)
        self.assertEqual(deadline.remaining_days, 2)
        self.assertEqual(deadline.color_class, "warning")
        self.assertTrue(deadline.automatic_due)
        self.assertEqual(send_case_deadline_reminder(deadline, self.actor), 3)
        self.assertEqual(
            set(WebNotification.objects.filter(spdp=spdp).values_list("recipient_id", flat=True)),
            {self.kasi.pk, self.staff.pk, self.kasubsi.pk},
        )

    @patch("notifications.services.send_whatsapp_message")
    @patch("notifications.services.send_telegram_message")
    def test_menu_configuration_controls_external_deadline_channels(
        self, send_telegram, send_whatsapp,
    ):
        NotificationSetting.objects.update_or_create(pk=1, defaults={
            "whatsapp_enabled": True,
            "telegram_enabled": True,
            "telegram_bot_token": "token-test",
            "outbound_message_delay_minutes": 5,
        })
        NotificationMenuSetting.objects.update_or_create(
            menu_key=NotificationMenuSetting.Menu.P16,
            defaults={"whatsapp_enabled": False, "telegram_enabled": True},
        )
        for index, recipient in enumerate((self.kasi, self.prosecutor, self.staff, self.kasubsi), start=1):
            recipient.whatsapp_number = f"0812345678{index}"
            recipient.telegram_chat_id = str(1000 + index)
            recipient.save(update_fields=("whatsapp_number", "telegram_chat_id"))
        send_telegram.return_value = ({"ok": True, "message_id": 10}, 200)
        send_whatsapp.return_value = ({"ok": True}, 200)

        deadline = case_deadline_for_spdp(self.spdp, self.today)
        self.assertEqual(send_case_deadline_reminder(deadline, self.actor), 4)
        send_telegram.assert_not_called()
        send_whatsapp.assert_not_called()
        telegram_logs = list(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.TELEGRAM,
        ).order_by("scheduled_at", "pk"))
        self.assertEqual(len(telegram_logs), 4)
        self.assertTrue(all(
            item.status == NotificationLog.Status.QUEUED for item in telegram_logs
        ))
        for previous, current in zip(telegram_logs, telegram_logs[1:]):
            self.assertGreaterEqual(
                current.scheduled_at - previous.scheduled_at,
                timedelta(minutes=5),
            )
        self.assertEqual(
            process_notification_queue(telegram_logs[0].scheduled_at), 1,
        )
        send_telegram.assert_called_once()
        telegram_logs[0].refresh_from_db()
        self.assertEqual(telegram_logs[0].status, NotificationLog.Status.SENT)
        self.assertFalse(
            NotificationLog.objects.filter(channel=NotificationLog.Channel.WHATSAPP).exists(),
        )

    def test_web_notification_can_be_disabled_per_stage(self):
        NotificationMenuSetting.objects.update_or_create(
            menu_key=NotificationMenuSetting.Menu.P16,
            defaults={"web_enabled": False},
        )
        deadline = case_deadline_for_spdp(self.spdp, self.today)

        self.assertEqual(send_case_deadline_reminder(deadline, self.actor), 4)
        self.assertFalse(WebNotification.objects.filter(spdp=self.spdp).exists())

    def test_stage_one_starts_seven_day_deadline(self):
        stage_one = StageOne.objects.create(
            spdp=self.spdp,
            case_file_number="BP/1/XI/2026",
            cover_letter_number="B/1/XI/2026",
            laws_and_articles="Pasal 362 KUHP",
            cover_letter_document=SimpleUploadedFile("pengantar.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
            created_by=self.actor,
        )
        StageOne.objects.filter(pk=stage_one.pk).update(
            completed_at=timezone.now() - timedelta(days=5),
        )
        self.spdp.refresh_from_db()
        deadline = case_deadline_for_spdp(self.spdp, self.today)
        self.assertEqual(deadline.stage_key, "stage1")
        self.assertEqual(deadline.period_days, 7)
        self.assertEqual(deadline.elapsed_days, 5)
        self.assertEqual(deadline.color_class, "warning")
        self.assertTrue(deadline.automatic_due)

    def test_stage_one_reminder_is_sent_on_day_five(self):
        stage_one = StageOne.objects.create(
            spdp=self.spdp,
            case_file_number="BP/2/XI/2026",
            cover_letter_number="B/2/XI/2026",
            laws_and_articles="Pasal 362 KUHP",
            cover_letter_document=SimpleUploadedFile("pengantar-2.pdf", b"%PDF-1.4\n%%EOF", content_type="application/pdf"),
            created_by=self.actor,
        )
        StageOne.objects.filter(pk=stage_one.pk).update(
            completed_at=timezone.now() - timedelta(days=5),
        )
        self.assertEqual(process_due_case_deadline_reminders(self.today), 1)
        dispatch = CaseReminderDispatch.objects.get(spdp=self.spdp, stage_key="stage1")
        self.assertEqual(dispatch.reminder_day, 5)
        self.assertEqual(dispatch.recipient_count, 4)

    def test_p19_starts_fourteen_day_deadline_and_reminds_on_day_twelve(self):
        draft = CaseDocumentDraft.create_for_spdp(
            self.spdp, CaseDocumentDraft.DocumentType.P19, self.actor,
        )
        draft.letter_number = "B-190/N.1.11/Um.1/11/2026"
        draft.letter_date = self.today - timedelta(days=12)
        draft.save(update_fields=("letter_number", "letter_date", "updated_at"))
        deadline = case_deadline_for_spdp(self.spdp, self.today)
        self.assertEqual(deadline.stage_key, "p19")
        self.assertEqual(deadline.period_days, 14)
        self.assertEqual(deadline.elapsed_days, 12)
        self.assertTrue(deadline.automatic_due)
        self.assertEqual(process_due_case_deadline_reminders(self.today), 1)
        self.assertTrue(CaseReminderDispatch.objects.filter(spdp=self.spdp, stage_key="p19", reminder_day=12).exists())

    def test_p21_starts_fourteen_day_deadline_and_reminds_on_day_twelve(self):
        draft = P21Draft.create_for_spdp(self.spdp, self.actor)
        draft.letter_number = "B-210/N.1.11/Um.1/11/2026"
        draft.letter_date = self.today - timedelta(days=12)
        draft.save(update_fields=("letter_number", "letter_date", "updated_at"))
        deadline = case_deadline_for_spdp(self.spdp, self.today)
        self.assertEqual(deadline.stage_key, "p21")
        self.assertEqual(deadline.period_days, 14)
        self.assertEqual(deadline.elapsed_days, 12)
        self.assertTrue(deadline.automatic_due)
        self.assertEqual(process_due_case_deadline_reminders(self.today), 1)
        self.assertTrue(CaseReminderDispatch.objects.filter(spdp=self.spdp, stage_key="p21", reminder_day=12).exists())

    def test_issued_sop_form_03_removes_case_from_active_deadline(self):
        sop03 = SOPForm03Draft.create_for_spdp(self.spdp, self.actor)
        sop03.letter_number = "B-300/N.1.11/Um.1/11/2026"
        sop03.save(update_fields=("letter_number", "updated_at"))
        self.assertIsNone(case_deadline_for_spdp(self.spdp, self.today))


class NotificationSettingAccessTests(TestCase):
    def setUp(self):
        admin_role, _ = Role.objects.get_or_create(code=Role.ADMIN, defaults={"name": "Admin", "sort_order": 20})
        super_role, _ = Role.objects.get_or_create(code=Role.SUPER_ADMIN, defaults={"name": "Super Admin", "sort_order": 10})
        self.admin = User.objects.create_user("admin-notif", "admin-notif@test.id", "rahasia-kuat")
        self.superadmin = User.objects.create_user("super-notif", "super-notif@test.id", "rahasia-kuat")
        self.admin.roles.add(admin_role)
        self.superadmin.roles.add(super_role)

    def test_admin_cannot_open_notification_settings(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("notifications:index")).status_code, 403)

    def test_only_superadmin_can_open_notification_template_settings(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("notifications:template_settings")).status_code, 403)

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("notifications:template_settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Setting Template Notifikasi")
        self.assertContains(response, "Penunjukan Jaksa P-16 - WhatsApp")
        self.assertContains(response, "SOP Form 2 - Telegram")
        self.assertContains(response, "SOP Form 3 Terbit - WhatsApp")
        self.assertEqual(NotificationTemplate.objects.count(), len(TEMPLATE_DEFINITIONS))

    def test_superadmin_can_configure_notification_channels_per_menu(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("notifications:menu_settings")).status_code, 403)

        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("notifications:menu_settings"))
        self.assertRedirects(response, reverse("notifications:template_settings"))
        response = self.client.get(
            reverse("notifications:template_settings") + "?edit=p16_deadline_whatsapp",
        )
        self.assertContains(response, "Konfigurasi Pengiriman")
        self.assertContains(response, "P-16")
        self.assertContains(response, "SOP Form 3")
        self.assertEqual(
            NotificationMenuSetting.objects.count(),
            len(NotificationMenuSetting.Menu.choices),
        )
        self.assertTrue(
            all(
                item.whatsapp_enabled and item.telegram_enabled
                for item in NotificationMenuSetting.objects.all()
            ),
        )

        response = self.client.post(reverse("notifications:template_settings"), {
            "template_key": "p16_deadline_whatsapp",
            "action": "save_template",
            "subject_template": TEMPLATE_DEFINITIONS["p16_deadline_whatsapp"]["subject"],
            "body_template": TEMPLATE_DEFINITIONS["p16_deadline_whatsapp"]["body"],
            "menu_whatsapp_enabled": "on",
        })
        self.assertEqual(response.status_code, 302)
        p16 = NotificationMenuSetting.objects.get(menu_key="p16")
        p17 = NotificationMenuSetting.objects.get(menu_key="p17")
        self.assertTrue(p16.whatsapp_enabled)
        self.assertFalse(p16.telegram_enabled)
        self.assertTrue(p17.whatsapp_enabled)
        self.assertTrue(p17.telegram_enabled)

    def test_web_template_editor_only_shows_web_active_toggle(self):
        self.client.force_login(self.superadmin)
        key = "p16_deadline_web"
        response = self.client.get(
            reverse("notifications:template_settings") + f"?edit={key}",
        )
        self.assertContains(response, 'name="menu_web_enabled"')
        self.assertNotContains(response, 'name="menu_whatsapp_enabled"')
        self.assertNotContains(response, 'name="menu_telegram_enabled"')

        response = self.client.post(reverse("notifications:template_settings"), {
            "template_key": key,
            "action": "save_template",
            "subject_template": TEMPLATE_DEFINITIONS[key]["subject"],
            "body_template": TEMPLATE_DEFINITIONS[key]["body"],
        })
        self.assertEqual(response.status_code, 302)
        setting = NotificationMenuSetting.objects.get(menu_key="p16")
        self.assertFalse(setting.web_enabled)
        self.assertTrue(setting.whatsapp_enabled)
        self.assertTrue(setting.telegram_enabled)

    def test_every_deadline_stage_has_complete_templates_for_all_channels(self):
        self.client.force_login(self.superadmin)
        self.client.get(reverse("notifications:template_settings"))
        for stage_key in DEADLINE_TEMPLATE_STAGES:
            for channel in ("web", "whatsapp", "telegram"):
                key = f"{stage_key}_deadline_{channel}"
                self.assertIn(key, TEMPLATE_DEFINITIONS)
                self.assertTrue(NotificationTemplate.objects.filter(key=key).exists())
                self.assertTrue(
                    {"daftar_pelaku", "daftar_jaksa", "daftar_pegawai"}.issubset(
                        TEMPLATE_DEFINITIONS[key]["variables"],
                    ),
                )
        for stage_key in DOCUMENT_ISSUED_STAGES:
            for channel in ("web", "whatsapp", "telegram"):
                key = issued_template_key(stage_key, channel)
                self.assertIn(key, TEMPLATE_DEFINITIONS)
                self.assertTrue(NotificationTemplate.objects.filter(key=key).exists())
                self.assertTrue(
                    {"daftar_pelaku", "daftar_jaksa", "daftar_pegawai"}.issubset(
                        TEMPLATE_DEFINITIONS[key]["variables"],
                    ),
                )

        self.assertEqual(
            set(NotificationMenuSetting.objects.values_list("menu_key", flat=True)),
            {key for key, _ in NotificationMenuSetting.Menu.choices},
        )
        investigator_template = NotificationTemplate.objects.get(
            key="p16_investigator_issued_whatsapp",
        )
        self.assertEqual(investigator_template.menu_key, "p16")
        self.assertIn("{nama_penyidik}", investigator_template.body_template)
        self.assertIn("{daftar_pelaku}", investigator_template.body_template)
        self.assertIn("{daftar_jaksa}", investigator_template.body_template)
        for key, definition in TEMPLATE_DEFINITIONS.items():
            combined = " ".join((
                definition["name"], definition["description"],
                definition["subject"], definition["body"],
            )).casefold()
            self.assertNotIn("otomatis", combined, key)
        for template in NotificationTemplate.objects.all():
            combined = " ".join((
                template.name, template.description,
                template.subject_template, template.body_template,
            )).casefold()
            self.assertNotIn("otomatis", combined, template.key)

    def test_superadmin_can_update_and_reset_notification_template(self):
        self.client.force_login(self.superadmin)
        self.client.get(reverse("notifications:template_settings"))
        template = NotificationTemplate.objects.get(key="p16_assignment_whatsapp")

        response = self.client.post(reverse("notifications:template_settings"), {
            "template_key": template.key,
            "action": "save_template",
            "subject_template": "Perkara {nomor_spdp}",
            "body_template": "Yth. {nama_penerima}, batas P-16 {batas_p16}.",
        })
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertEqual(template.subject_template, "Perkara {nomor_spdp}")
        self.assertEqual(template.updated_by, self.superadmin)
        rendered = render_notification_template(template.key, {
            "nama_penerima": "Kasi Pidum",
            "nomor_spdp": "B/123/IX/2026",
            "tanggal_diterima": "26 September 2026",
            "jumlah_pelaku": "1 orang",
            "batas_p16": "29 September 2026",
            "status_waktu": "tersisa 3 hari",
            "diteruskan_oleh": "Admin",
        })
        self.assertEqual(rendered["subject"], "Perkara B/123/IX/2026")
        self.assertIn("Kasi Pidum", rendered["body"])

        response = self.client.post(reverse("notifications:template_settings"), {
            "template_key": template.key,
            "action": "reset_template",
        })
        self.assertEqual(response.status_code, 302)
        template.refresh_from_db()
        self.assertTrue(template.is_default)

    def test_notification_template_rejects_unknown_variable(self):
        self.client.force_login(self.superadmin)
        self.client.get(reverse("notifications:template_settings"))
        template = NotificationTemplate.objects.get(key="p16_assignment_web")
        response = self.client.post(reverse("notifications:template_settings"), {
            "template_key": template.key,
            "action": "save_template",
            "subject_template": "P-16 {variabel_tidak_ada}",
            "body_template": "SPDP {nomor_spdp}",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Variabel tidak tersedia")

    def test_superadmin_can_save_notification_settings(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("notifications:index"), {
            "action": "save_telegram",
            "telegram-telegram_enabled": "on",
            "telegram-telegram_bot_token": "123456:secret-token",
            "telegram-telegram_default_chat_id": "987654321",
        })
        self.assertRedirects(response, reverse("notifications:index"))
        response = self.client.post(reverse("notifications:index"), {
            "action": "save_whatsapp",
            "whatsapp-whatsapp_enabled": "on",
        })
        self.assertRedirects(response, reverse("notifications:index"))
        setting = NotificationSetting.objects.get(pk=1)
        self.assertTrue(setting.telegram_enabled)
        self.assertTrue(setting.whatsapp_enabled)
        self.assertEqual(setting.whatsapp_connection_status, NotificationSetting.WhatsAppStatus.NEED_LOGIN)
        self.assertEqual(setting.updated_by, self.superadmin)

    def test_superadmin_can_set_automatic_notification_time_from_popup(self):
        self.client.force_login(self.superadmin)
        page = self.client.get(reverse("notifications:index"))
        self.assertContains(page, "Setting Notifikasi")
        self.assertContains(page, 'id="automatic-settings-modal"')
        self.assertContains(page, 'type="time"')
        self.assertContains(page, "Jeda antar pesan (menit)")
        self.assertContains(page, 'type="number"')

        response = self.client.post(reverse("notifications:index"), {
            "action": "save_automatic",
            "automatic-automatic_notification_enabled": "on",
            "automatic-automatic_notification_time": "09:30",
            "automatic-outbound_message_delay_minutes": "7",
        })
        self.assertRedirects(response, reverse("notifications:index"))
        setting = NotificationSetting.objects.get(pk=1)
        self.assertTrue(setting.automatic_notification_enabled)
        self.assertEqual(setting.automatic_notification_time.strftime("%H:%M"), "09:30")
        self.assertEqual(setting.outbound_message_delay_minutes, 7)
        self.assertEqual(setting.updated_by, self.superadmin)

    def test_legacy_notification_settings_post_still_supported(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("notifications:settings"), {
            "telegram_enabled": "on",
            "telegram_bot_token": "123456:secret-token",
            "telegram_default_chat_id": "987654321",
            "whatsapp_enabled": "on",
        })
        self.assertRedirects(response, reverse("notifications:index"))
        setting = NotificationSetting.objects.get(pk=1)
        self.assertTrue(setting.telegram_enabled)
        self.assertTrue(setting.whatsapp_enabled)

    def test_superadmin_sees_notification_dashboard_page(self):
        NotificationSetting.objects.update_or_create(
            pk=1,
            defaults={
                "whatsapp_enabled": True,
                "whatsapp_connection_status": NotificationSetting.WhatsAppStatus.ACTIVE,
            },
        )
        NotificationLog.objects.create(
            channel=NotificationLog.Channel.WHATSAPP,
            recipient="628123456789",
            recipient_name="Kasi Pidum",
            subject="Tes Log",
            message="Isi pesan log",
            status=NotificationLog.Status.SENT,
            triggered_by=self.superadmin,
        )
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("notifications:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total Pesan WhatsApp")
        self.assertContains(response, "Total Pesan Telegram")
        self.assertContains(response, "Log Pengiriman")
        self.assertContains(response, "Setting WhatsApp")
        self.assertContains(response, "Setting Telegram")
        self.assertContains(response, "telegram-test-button")
        self.assertContains(response, "telegram-fetch-chat-button")
        self.assertContains(response, "Kasi Pidum")
        self.assertContains(response, "Tes Log")
        self.assertContains(response, 'id="wa-start-button" disabled')
        self.assertContains(response, "Session Aktif")
        self.assertContains(response, "Setting Notifikasi")
        self.assertNotContains(response, "Buka Wa-Gateway")
        self.assertNotContains(response, "Admin scan")

    def test_superadmin_can_cancel_all_queued_notifications(self):
        queued_whatsapp = NotificationLog.objects.create(
            channel=NotificationLog.Channel.WHATSAPP,
            recipient="628111111111",
            recipient_name="Penerima WhatsApp",
            subject="Antrean WhatsApp",
            message="Pesan antrean WhatsApp",
            status=NotificationLog.Status.QUEUED,
            scheduled_at=timezone.now() + timedelta(minutes=2),
        )
        queued_telegram = NotificationLog.objects.create(
            channel=NotificationLog.Channel.TELEGRAM,
            recipient="123456",
            recipient_name="Penerima Telegram",
            subject="Antrean Telegram",
            message="Pesan antrean Telegram",
            status=NotificationLog.Status.QUEUED,
            scheduled_at=timezone.now() + timedelta(minutes=4),
        )
        sent = NotificationLog.objects.create(
            channel=NotificationLog.Channel.WHATSAPP,
            recipient="628222222222",
            subject="Sudah terkirim",
            message="Pesan sudah terkirim",
            status=NotificationLog.Status.SENT,
        )
        processing = NotificationLog.objects.create(
            channel=NotificationLog.Channel.TELEGRAM,
            recipient="654321",
            subject="Sedang diproses",
            message="Pesan sedang diproses",
            status=NotificationLog.Status.PROCESSING,
        )
        self.client.force_login(self.superadmin)

        page = self.client.get(reverse("notifications:index"))
        self.assertContains(page, "Hentikan Antrean (2)")
        response = self.client.post(reverse("notifications:index"), {
            "action": "cancel_queue",
        })
        self.assertRedirects(response, reverse("notifications:index"))

        queued_whatsapp.refresh_from_db()
        queued_telegram.refresh_from_db()
        sent.refresh_from_db()
        processing.refresh_from_db()
        self.assertEqual(queued_whatsapp.status, NotificationLog.Status.CANCELLED)
        self.assertEqual(queued_telegram.status, NotificationLog.Status.CANCELLED)
        self.assertIsNone(queued_whatsapp.scheduled_at)
        self.assertIn(self.superadmin.display_name, queued_whatsapp.error_message)
        self.assertEqual(sent.status, NotificationLog.Status.SENT)
        self.assertEqual(processing.status, NotificationLog.Status.PROCESSING)

    def test_failed_status_opens_failure_reason_modal(self):
        NotificationLog.objects.create(
            channel=NotificationLog.Channel.TELEGRAM,
            recipient="987654321",
            recipient_name="Kasi Pidum",
            subject="Reminder P-16",
            message="Isi reminder",
            status=NotificationLog.Status.FAILED,
            error_message="Bot Telegram tidak dapat menghubungi Chat ID penerima.",
            context_label="SPDP B/123/2026",
            attempted_at=timezone.now(),
        )
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("notifications:index"))
        self.assertContains(response, "data-notification-failure")
        self.assertContains(response, 'id="notification-failure-modal"')
        self.assertContains(response, "Bot Telegram tidak dapat menghubungi Chat ID penerima.")
        self.assertContains(response, "Penyebab kegagalan")

    @override_settings(WA_GATEWAY_URL="http://127.0.0.1:39999")
    def test_superadmin_gets_json_when_gateway_offline(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("notifications:whatsapp_status"))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ok"])

    @override_settings(WA_GATEWAY_URL="http://127.0.0.1:39999")
    def test_superadmin_gets_json_when_test_message_gateway_offline(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("notifications:whatsapp_test_message"))
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(NotificationLog.objects.filter(channel=NotificationLog.Channel.WHATSAPP, status=NotificationLog.Status.FAILED).exists())

    def test_whatsapp_logout_sends_telegram_alert_to_admin(self):
        self.client.force_login(self.superadmin)
        NotificationSetting.objects.update_or_create(
            pk=1,
            defaults={
                "telegram_enabled": True,
                "telegram_bot_token": "123456:secret-token",
                "telegram_default_chat_id": "987654321",
                "whatsapp_enabled": True,
            },
        )
        gateway_payload = {
            "ok": True,
            "status": "need_login",
            "message": "Session WhatsApp berhasil logout.",
        }
        telegram_payload = {
            "ok": True,
            "message": "Alert logout WhatsApp terkirim ke Telegram admin.",
            "result": {"message_id": 456},
            "message_id": 456,
        }

        with patch("notifications.views._gateway_request", return_value=(gateway_payload, 200)) as mocked_gateway:
            with patch("notifications.views.send_whatsapp_logout_telegram_alert", return_value=(telegram_payload, 200)) as mocked_telegram:
                response = self.client.post(reverse("notifications:whatsapp_logout"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        mocked_gateway.assert_called_once()
        mocked_telegram.assert_called_once()
        self.assertTrue(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.TELEGRAM,
            status=NotificationLog.Status.SENT,
            recipient="987654321",
            subject="WhatsApp Gateway Logout",
            provider_message_id="456",
        ).exists())

    def test_whatsapp_monitor_alerts_when_session_becomes_logged_out(self):
        NotificationSetting.objects.update_or_create(
            pk=1,
            defaults={
                "telegram_enabled": True,
                "telegram_bot_token": "123456:secret-token",
                "telegram_default_chat_id": "987654321",
                "whatsapp_enabled": True,
                "whatsapp_connection_status": NotificationSetting.WhatsAppStatus.ACTIVE,
            },
        )
        gateway_payload = {
            "ok": True,
            "status": "need_login",
        }
        telegram_payload = {
            "ok": True,
            "message": "Alert logout WhatsApp terkirim ke Telegram admin.",
            "result": {"message_id": 789},
            "message_id": 789,
        }

        with patch("notifications.management.commands.monitor_whatsapp_session._gateway_request", return_value=(gateway_payload, 200)):
            with patch("notifications.management.commands.monitor_whatsapp_session.send_whatsapp_logout_telegram_alert", return_value=(telegram_payload, 200)):
                call_command("monitor_whatsapp_session", once=True)

        setting = NotificationSetting.objects.get(pk=1)
        self.assertEqual(setting.whatsapp_connection_status, NotificationSetting.WhatsAppStatus.NEED_LOGIN)
        self.assertEqual(setting.whatsapp_last_alert_status, NotificationSetting.WhatsAppStatus.NEED_LOGIN)
        self.assertIsNotNone(setting.whatsapp_last_alert_at)
        self.assertTrue(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.TELEGRAM,
            status=NotificationLog.Status.SENT,
            recipient="987654321",
            subject="WhatsApp Gateway Logout Otomatis",
            provider_message_id="789",
        ).exists())

    def test_superadmin_gets_json_when_telegram_setting_incomplete(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("notifications:telegram_test_message"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(NotificationLog.objects.filter(channel=NotificationLog.Channel.TELEGRAM, status=NotificationLog.Status.FAILED).exists())

    def test_superadmin_can_send_telegram_test_message(self):
        self.client.force_login(self.superadmin)
        telegram_payload = {
            "ok": True,
            "message": "Pesan tes Telegram terkirim ke Chat ID 987654321.",
            "result": {"message_id": 123},
            "message_id": 123,
        }

        with patch("notifications.views.send_telegram_message", return_value=(telegram_payload, 200)) as mocked_send:
            response = self.client.post(
                reverse("notifications:telegram_test_message"),
                data=json.dumps({"bot_token": "123456:secret-token", "chat_id": "987654321"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        mocked_send.assert_called_once()
        self.assertTrue(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.TELEGRAM,
            status=NotificationLog.Status.SENT,
            recipient="987654321",
            provider_message_id="123",
        ).exists())

    def test_superadmin_can_fetch_latest_telegram_chat_id_for_user(self):
        self.client.force_login(self.superadmin)
        NotificationSetting.objects.update_or_create(
            pk=1,
            defaults={"telegram_bot_token": "123456:secret-token"},
        )
        get_updates_response = mock_json_response({
            "ok": True,
            "result": [
                {
                    "update_id": 10,
                    "message": {
                        "message_id": 77,
                        "chat": {"id": 987654321, "first_name": "Kasi", "last_name": "Pidum"},
                        "text": "/start",
                    },
                },
            ],
        })
        send_message_payload = {
            "ok": True,
            "message": "Balasan /start terkirim ke Chat ID 987654321.",
            "result": {"message_id": 88},
            "message_id": 88,
        }

        with patch("notifications.views.urlrequest.urlopen", return_value=get_updates_response) as mocked_updates:
            with patch("notifications.views.send_telegram_message", return_value=(send_message_payload, 200)) as mocked_send:
                response = self.client.post(
                    reverse("notifications:telegram_fetch_chat_id"),
                    data=json.dumps({"user_id": self.admin.id}),
                    content_type="application/json",
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("bot sudah membalas /start", response.json()["message"])
        mocked_updates.assert_called_once()
        mocked_send.assert_called_once()
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.telegram_chat_id, "987654321")
        self.assertEqual(NotificationSetting.objects.get(pk=1).telegram_default_chat_id, "987654321")
        self.assertTrue(NotificationLog.objects.filter(
            channel=NotificationLog.Channel.TELEGRAM,
            status=NotificationLog.Status.SENT,
            recipient="987654321",
            subject="Balasan /start Telegram",
            provider_message_id="88",
        ).exists())
