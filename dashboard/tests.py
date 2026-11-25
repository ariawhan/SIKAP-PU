from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import Role, User
from cases.models import CaseDocumentDraft, P16Assignment, P16Draft, P21Draft, SOPForm03Draft, SPDP
from notifications.models import WebNotification

class AccessTests(TestCase):
    def setUp(self):
        self.roles = {
            code: Role.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})[0]
            for code, name, order in ((Role.SUPER_ADMIN, "Super Admin", 10), (Role.ADMIN, "Admin", 20), (Role.KASI_PIDUM, "Kasi Pidum", 30), (Role.PROSECUTOR, "Jaksa", 40), (Role.EMPLOYEE, "Pegawai", 50))
        }
        self.admin = self.make_user("admin", "admin@test.id", Role.ADMIN)
        self.superadmin = self.make_user("super", "super@test.id", Role.SUPER_ADMIN)
        self.kasi_pidum = self.make_user("kasi", "kasi@test.id", Role.KASI_PIDUM)
        self.prosecutor = self.make_user("jaksa", "jaksa@test.id", Role.PROSECUTOR)
        self.employee = self.make_user("pegawai", "pegawai@test.id", Role.EMPLOYEE)

    def make_user(self, username, email, *role_codes):
        user = User.objects.create_user(username, email, "rahasia-kuat")
        user.roles.add(*(self.roles[code] for code in role_codes))
        return user
    def test_login_with_email(self):
        response = self.client.post(reverse("accounts:login"), {"username": "admin@test.id", "password": "rahasia-kuat"})
        self.assertRedirects(response, reverse("dashboard:index"))
    def test_admin_forbidden_from_users(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:users")).status_code, 403)
    def test_superadmin_can_open_users(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("dashboard:users"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ubah Password")
        self.assertContains(response, 'name="action" value="change_password"')

    def test_dashboard_contains_accessible_theme_toggle(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "Aktifkan mode gelap")
        self.assertContains(response, "dark-mode.css")

    def test_dashboard_contains_web_notification_dropdown(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "web-notifications.css")
        self.assertContains(response, "data-web-notification-toggle")
        self.assertContains(response, "Notifikasi Aplikasi")
        self.assertContains(response, "Tandai dibaca")
        self.assertContains(response, "Belum ada notifikasi")
        self.assertContains(response, "data-web-notification-count hidden")

    def test_dashboard_returned_cases_stat_sums_sop03_p20_and_sop07(self):
        today = timezone.localdate()

        def make_spdp(suffix):
            return SPDP.objects.create(
                investigator_agency="Kepolisian RI",
                investigating_unit="Satreskrim",
                investigation_order_number=f"SP.Sidik/{suffix}/2026",
                investigation_order_date=today,
                letter_number=f"B/SPDP/DASHBOARD/{suffix}/2026",
                letter_date=today,
                received_date=today,
                case_summary="Perkara uji dashboard.",
                laws_and_articles="Pasal 362 KUHP",
            )

        sop03_spdp = make_spdp("SOP03")
        SOPForm03Draft.objects.create(
            spdp=sop03_spdp,
            letter_number="DRAFT/SOP03/DASHBOARD/2026",
            letter_date=today,
        )
        for suffix, document_type in (
            ("P20", CaseDocumentDraft.DocumentType.P20),
            ("SOP07", CaseDocumentDraft.DocumentType.SOP_FORM_07),
            ("P18", CaseDocumentDraft.DocumentType.P18),
        ):
            CaseDocumentDraft.objects.create(
                spdp=make_spdp(suffix),
                document_type=document_type,
                letter_number=f"DRAFT/{suffix}/DASHBOARD/2026",
                letter_date=today,
            )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.context["stats"]["returned"], {
            "total": 3,
            "year": 3,
            "month": 3,
        })
        self.assertContains(response, "Perkara Dikembalikan")
        self.assertContains(response, "SOP Form 3, P-20, dan SOP Form 7")
        self.assertNotContains(response, "Total P-16")

    def test_dashboard_total_p21_counts_completed_cases_not_stopped(self):
        today = timezone.localdate()

        def make_spdp(suffix):
            return SPDP.objects.create(
                investigator_agency="Kepolisian RI",
                investigating_unit="Satreskrim",
                investigation_order_number=f"SP.Sidik/P21-{suffix}/2026",
                investigation_order_date=today,
                letter_number=f"B/SPDP/DASHBOARD/P21-{suffix}/2026",
                letter_date=today,
                received_date=today,
                case_summary="Perkara uji kartu total P-21.",
                laws_and_articles="Pasal 362 KUHP",
            )

        def make_p21(suffix, *, completed=True):
            return P21Draft.objects.create(
                spdp=make_spdp(suffix),
                letter_number=f"B/P-21/{suffix}/2026",
                letter_date=today,
                status=(
                    P21Draft.Status.COMPLETED
                    if completed else P21Draft.Status.DRAFT
                ),
            )

        make_p21("ACTIVE")
        sop07_draft_p21 = make_p21("SOP7-DRAFT")
        CaseDocumentDraft.objects.create(
            spdp=sop07_draft_p21.spdp,
            document_type=CaseDocumentDraft.DocumentType.SOP_FORM_07,
            letter_number="DRAFT/SOP-FORM-07/2026",
            letter_date=today,
        )
        sop03_p21 = make_p21("SOP3-ISSUED")
        SOPForm03Draft.objects.create(
            spdp=sop03_p21.spdp,
            letter_number="B/SOP-03/ISSUED/2026",
            letter_date=today,
        )
        p20_p21 = make_p21("P20-UPLOADED")
        CaseDocumentDraft.objects.create(
            spdp=p20_p21.spdp,
            document_type=CaseDocumentDraft.DocumentType.P20,
            letter_number="B/P-20/UPLOADED/2026",
            letter_date=today,
            sipede_status=CaseDocumentDraft.SipedeStatus.UPLOADED,
        )
        sop07_issued_p21 = make_p21("SOP7-ISSUED")
        CaseDocumentDraft.objects.create(
            spdp=sop07_issued_p21.spdp,
            document_type=CaseDocumentDraft.DocumentType.SOP_FORM_07,
            letter_number="B/SOP-07/ISSUED/2026",
            letter_date=today,
        )
        make_p21("NOT-COMPLETED", completed=False)

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))

        self.assertEqual(response.context["stats"]["p21"], {
            "total": 2,
            "year": 2,
            "month": 2,
        })
        self.assertContains(response, "P-21 selesai dilaksanakan; perkara belum diberhentikan")

    def test_dashboard_chart_uses_document_dates_for_workflow_stages(self):
        today = timezone.localdate()
        previous_month = (today.replace(day=1) - timedelta(days=1)).replace(day=15)
        spdp = SPDP.objects.create(
            investigator_agency="Kepolisian RI",
            investigating_unit="Satreskrim",
            investigation_order_number="SP.Sidik/CHART/2026",
            investigation_order_date=today,
            letter_number="B/SPDP/DASHBOARD/CHART/2026",
            letter_date=today,
            received_date=today,
            case_summary="Perkara uji grafik.",
            laws_and_articles="Pasal 362 KUHP",
        )
        CaseDocumentDraft.objects.create(
            spdp=spdp,
            document_type=CaseDocumentDraft.DocumentType.P20,
            letter_number="DRAFT/P20/DASHBOARD/CHART/2026",
            letter_date=previous_month,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))

        months = response.context["chart"]["months"]
        self.assertEqual([month["label"] for month in months], [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember",
        ])
        self.assertTrue(all(month["year"] == today.year for month in months))
        self.assertEqual(months[previous_month.month - 1]["stages"]["p20"], 1)
        self.assertEqual(months[today.month - 1]["total"], 1)
        self.assertContains(response, 'class="dev-line-total"')
        self.assertContains(response, 'class="dev-line-stage"')
        self.assertEqual(response.content.count(b'class="dev-line-stage"'), 10)
        self.assertNotContains(response, "dev-bar-stage")

    def test_dashboard_recent_cases_show_current_workflow_stage_and_status(self):
        today = timezone.localdate()

        def make_spdp(suffix):
            return SPDP.objects.create(
                investigator_agency="Kepolisian RI",
                investigating_unit="Satreskrim",
                investigation_order_number=f"SP.Sidik/RECENT-{suffix}/2026",
                investigation_order_date=today,
                letter_number=f"B/SPDP/DASHBOARD/RECENT-{suffix}/2026",
                letter_date=today,
                received_date=today,
                case_summary="Perkara uji tahap terbaru.",
                laws_and_articles="Pasal 362 KUHP",
            )

        completed_spdp = make_spdp("COMPLETED")
        P21Draft.objects.create(
            spdp=completed_spdp,
            letter_number="B/P-21/RECENT-COMPLETED/2026",
            letter_date=today,
            status=P21Draft.Status.COMPLETED,
        )
        p20_spdp = make_spdp("P20")
        CaseDocumentDraft.objects.create(
            spdp=p20_spdp,
            document_type=CaseDocumentDraft.DocumentType.P20,
            letter_number="DRAFT/P-20/RECENT/2026",
            letter_date=today,
        )
        sop07_spdp = make_spdp("SOP7")
        P21Draft.objects.create(
            spdp=sop07_spdp,
            letter_number="B/P-21/RECENT-SOP7/2026",
            letter_date=today,
        )
        CaseDocumentDraft.objects.create(
            spdp=sop07_spdp,
            document_type=CaseDocumentDraft.DocumentType.SOP_FORM_07,
            letter_number="B/SOP-07/RECENT/2026",
            letter_date=today,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        recent_cases = {
            row["spdp"].pk: row for row in response.context["recent_cases"]
        }

        self.assertEqual(
            (recent_cases[completed_spdp.pk]["stage"],
             recent_cases[completed_spdp.pk]["status"]),
            ("P-21", "Sudah P-21"),
        )
        self.assertEqual(
            (recent_cases[p20_spdp.pk]["stage"], recent_cases[p20_spdp.pk]["status"]),
            ("P-20", "Proses P-20"),
        )
        self.assertEqual(
            (recent_cases[sop07_spdp.pk]["stage"],
             recent_cases[sop07_spdp.pk]["status"],
             recent_cases[sop07_spdp.pk]["color"]),
            ("SOP Form 7", "Diberhentikan", "red"),
        )
        self.assertContains(response, "Perkara Terbaru")

    def test_dashboard_reminder_card_links_to_active_stage_editor(self):
        today = timezone.localdate()
        spdp = SPDP.objects.create(
            investigator_agency="Kepolisian RI",
            investigating_unit="Satreskrim",
            investigation_order_number="SP.Sidik/REMINDER/2026",
            investigation_order_date=today - timedelta(days=30),
            letter_number="B/SPDP/DASHBOARD/REMINDER/2026",
            letter_date=today - timedelta(days=29),
            received_date=today - timedelta(days=28),
            case_summary="Perkara uji reminder.",
            laws_and_articles="Pasal 362 KUHP",
        )
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=self.kasi_pidum,
            started_by=self.admin,
            status=P16Assignment.Status.ASSIGNED,
        )
        p16, _ = P16Draft.create_for_assignment(assignment, self.kasi_pidum)
        p16.draft_number = "B/P16/DASHBOARD/REMINDER/2026"
        p16.letter_date = today - timedelta(days=20)
        p16.save(update_fields=("draft_number", "letter_date", "updated_at"))

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))

        expected_url = reverse("cases:p16_draft_detail", args=[p16.pk])
        self.assertContains(response, f'class="dev-reminder-link" href="{expected_url}"')
        self.assertContains(response, f"P-16 · {spdp.letter_number}")
        self.assertContains(
            response,
            '<span class="deadline-badge-value">Sisa 10 hari</span>',
        )
        self.assertNotContains(response, '<span class="deadline-badge-label">')
        self.assertContains(response, "Masa 30 hari · batas")

    def test_user_sees_and_can_mark_own_web_notification_as_read(self):
        notification = WebNotification.objects.create(
            recipient=self.admin,
            title="Tugas Penunjukan Jaksa P-16",
            message="SPDP B/01 menunggu penunjukan Jaksa.",
            target_url=reverse("cases:spdp_list"),
            created_by=self.superadmin,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Tugas Penunjukan Jaksa P-16")
        self.assertContains(response, "SPDP B/01 menunggu penunjukan Jaksa.")
        self.assertContains(response, 'class="web-notification-item unread"')
        self.assertContains(response, ">1</span>")

        response = self.client.post(reverse("notifications:mark_web_notifications_read"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_dashboard_loads_logo_and_responsive_styles(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Logo-Pidum.png")
        self.assertContains(response, "responsive.css")
        self.assertContains(response, 'name="viewport"')

    def test_dashboard_contains_application_footer_version(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "footer.css")
        self.assertContains(response, "SIKAP-PU")
        self.assertContains(
            response,
            "SISTEM INFORMASI KENDALI ADMINISTRASI PERKARA TINDAK PIDANA UMUM PADA TAHAP PRA PENUNTUTAN BERBASIS WEB DENGAN AUTOMATIC REMINDER WHATSAPP DAN TELEGRAM",
        )
        self.assertContains(response, "Versi 1.0.0")

    def test_sidebar_has_toggle_close_and_scroll_support(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "data-menu-toggle")
        self.assertContains(response, "data-sidebar-close")
        self.assertContains(response, "sidebar-nav")
        self.assertContains(response, "sidebar.css")
        self.assertContains(response, "/static/vendor/tailwind-browser.js")
        self.assertNotContains(response, "cdn.jsdelivr.net/npm/@tailwindcss")

    def test_sidebar_menu_is_cleaned_and_uses_dropdowns(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "Settings")
        self.assertContains(response, "data-sidebar-dropdown")
        self.assertContains(response, "data-sidebar-dropdown-toggle")
        self.assertContains(response, "Pra Penuntutan")
        self.assertContains(response, "Konfigurasi")
        self.assertContains(response, "Integrasi")
        self.assertNotContains(response, "Penuntutan</a>")
        self.assertNotContains(response, "Eksekusi</a>")
        self.assertNotContains(response, ">Dokumen</a>")
        self.assertNotContains(response, "Jadwal Sidang</a>")
        self.assertNotContains(response, "Laporan</a>")
        self.assertNotContains(response, "Administrasi</a>")

    def test_sidebar_dropdowns_are_closed_by_default(self):
        self.client.force_login(self.superadmin)
        response = self.client.get(reverse("dashboard:index"))
        self.assertNotContains(response, 'sidebar-dropdown open')
        self.assertEqual(response.content.decode().count('data-sidebar-dropdown-toggle aria-expanded="false"'), 3)

    def test_all_operational_accounts_can_open_integration(self):
        for account in (self.admin, self.kasi_pidum, self.prosecutor, self.employee):
            self.client.force_login(account)
            response = self.client.get(reverse("dashboard:index"))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "<b>Integrasi</b>", html=True)
            self.assertContains(response, "Integrasi SIPede")
            self.assertNotContains(response, "Integrasi CMS")
            self.assertEqual(self.client.get(reverse("configurations:sipede_integration")).status_code, 200)
            self.assertEqual(self.client.get(reverse("configurations:cms_integration")).status_code, 200)
            self.client.logout()

    def test_jaksa_and_pegawai_cannot_manage_users(self):
        for account in (self.prosecutor, self.employee):
            self.client.force_login(account)
            self.assertEqual(self.client.get(reverse("dashboard:users")).status_code, 403)
            self.client.logout()

    def test_superadmin_can_create_jaksa_and_pegawai(self):
        self.client.force_login(self.superadmin)
        for role in ("jaksa", "pegawai"):
            response = self.client.post(reverse("dashboard:users"), {
                "first_name": role.title(),
                "last_name": "Pidum",
                "username": f"new-{role}",
                "email": f"new-{role}@test.id",
                "roles": [self.roles[role].pk],
                "password1": "Sandi-kuat-12345",
                "password2": "Sandi-kuat-12345",
            })
            self.assertRedirects(response, reverse("dashboard:users"))
            self.assertTrue(User.objects.filter(username=f"new-{role}", roles__code=role).exists())

    def test_user_can_have_kasi_pidum_and_jaksa_roles(self):
        kasi_jaksa = self.make_user("kasi-jaksa", "kasi-jaksa@test.id", Role.KASI_PIDUM, Role.PROSECUTOR)
        self.assertEqual(set(kasi_jaksa.roles.values_list("code", flat=True)), {Role.KASI_PIDUM, Role.PROSECUTOR})
        self.assertIn("Kasi Pidum", kasi_jaksa.role_labels)
        self.assertIn("Jaksa", kasi_jaksa.role_labels)

    def test_superadmin_can_change_user_password(self):
        self.client.force_login(self.superadmin)
        response = self.client.post(reverse("dashboard:users"), {
            "action": "change_password",
            "user_id": self.employee.pk,
            "new_password1": "Password-Baru-12345",
            "new_password2": "Password-Baru-12345",
        })
        self.assertRedirects(response, reverse("dashboard:users"))
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password("Password-Baru-12345"))
