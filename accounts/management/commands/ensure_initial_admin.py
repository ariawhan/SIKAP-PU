import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.models import Role


class Command(BaseCommand):
    help = "Membuat Super Admin awal hanya jika database belum memiliki pengguna."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.exists():
            self.stdout.write("[OK] Akun pengguna sudah tersedia.")
            return

        username = os.getenv("INITIAL_ADMIN_USERNAME", "superadmin")
        email = os.getenv("INITIAL_ADMIN_EMAIL", "superadmin@kejaksaan.go.id")
        configured_password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
        password = configured_password or secrets.token_urlsafe(12)
        account = User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            first_name="Super",
            last_name="Admin",
        )
        role, _ = Role.objects.get_or_create(code=Role.SUPER_ADMIN, defaults={"name": "Super Admin", "sort_order": 10})
        account.roles.add(role)
        self.stdout.write(self.style.SUCCESS("[OK] Super Admin pertama berhasil dibuat."))
        self.stdout.write(f"     Username : {username}")
        self.stdout.write(f"     Password : {password}")
        if not configured_password:
            self.stdout.write(self.style.WARNING("     Simpan password ini; password acak hanya ditampilkan sekali."))
