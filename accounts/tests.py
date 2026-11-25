from django.test import TestCase
from django.urls import reverse

from .models import Role, User


class ProfileTests(TestCase):
    def setUp(self):
        self.role, _ = Role.objects.get_or_create(
            code=Role.EMPLOYEE,
            defaults={"name": "Pegawai", "sort_order": 50},
        )
        self.user = User.objects.create_user(
            username="profil-user", email="profil@test.id",
            password="rahasia-kuat", first_name="Profil Lama",
        )
        self.user.roles.add(self.role)

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertRedirects(response, f'{reverse("accounts:login")}?next={reverse("accounts:profile")}')

    def test_header_has_profile_dropdown(self):
        self.user.photo = "users/photos/foto-profil.jpg"
        self.user.photo_position_x = 34
        self.user.photo_position_y = 61
        self.user.save(update_fields=["photo", "photo_position_x", "photo_position_y"])
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:index"))
        self.assertContains(response, "data-header-profile-toggle")
        self.assertContains(response, "Edit Profil")
        self.assertContains(response, "Logout")
        self.assertContains(response, reverse("accounts:profile"))
        self.assertContains(response, "/media/users/photos/foto-profil.jpg")
        self.assertContains(response, "object-position: 34% 61%")

    def test_user_can_update_own_profile(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "first_name": "Profil Baru", "email": "profil-baru@test.id",
            "nip": "1987654321", "nrp": "123456", "rank": "Penata",
            "grade": "III/c", "whatsapp_number": "628123456789",
            "telegram_chat_id": "99887766", "photo_position_x": "35",
            "photo_position_y": "62",
        })
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Profil Baru")
        self.assertEqual(self.user.email, "profil-baru@test.id")
        self.assertEqual(self.user.photo_position_x, 35)
        self.assertEqual(self.user.photo_position_y, 62)
        self.assertEqual(list(self.user.roles.values_list("code", flat=True)), [Role.EMPLOYEE])

    def test_profile_rejects_duplicate_email(self):
        User.objects.create_user(username="lain", email="dipakai@test.id", password="rahasia-kuat")
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:profile"), {
            "first_name": "Profil Lama", "email": "dipakai@test.id", "grade": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email sudah digunakan oleh pengguna lain.")
