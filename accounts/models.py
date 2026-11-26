from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    KASI_PIDUM = "kasi_pidum"
    KASUBSI_PREPROSECUTION = "kasubsi_prapenuntutan"
    PROSECUTOR = "jaksa"
    EMPLOYEE = "pegawai"

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name


class User(AbstractUser):
    email = models.EmailField("email", unique=True)
    nip = models.CharField("NIP", max_length=30, blank=True)
    nrp = models.CharField("NRP", max_length=30, blank=True)
    rank = models.CharField("Pangkat", max_length=120, blank=True)
    grade = models.CharField("Golongan", max_length=10, blank=True)
    position = models.CharField("Jabatan", max_length=160, blank=True)
    whatsapp_number = models.CharField("Nomor WhatsApp", max_length=30, blank=True)
    photo = models.ImageField("Foto", upload_to="users/photos/", blank=True, null=True)
    photo_position_x = models.PositiveSmallIntegerField("Posisi foto X", default=50)
    photo_position_y = models.PositiveSmallIntegerField("Posisi foto Y", default=50)
    roles = models.ManyToManyField(Role, related_name="users", blank=True, verbose_name="Role")
    telegram_chat_id = models.CharField("Chat ID Telegram", max_length=120, blank=True)

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_super_admin(self):
        return self.is_superuser or self.roles.filter(code=Role.SUPER_ADMIN).exists()

    @property
    def role_labels(self):
        labels = list(self.roles.values_list("name", flat=True))
        return ", ".join(labels) if labels else "Belum ada role"

    def has_role(self, *codes):
        return self.is_superuser or self.roles.filter(code__in=codes).exists()
