from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

USER_MODEL = settings.AUTH_USER_MODEL


class SingletonModel(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class InstitutionConfiguration(SingletonModel):
    institution_name = models.CharField("Nama instansi", max_length=180, default="Kejaksaan Republik Indonesia")
    work_unit = models.CharField("Satuan kerja", max_length=180, blank=True)
    institution_code = models.CharField("Kode instansi", max_length=30, blank=True)
    address = models.TextField("Alamat", blank=True)
    city = models.CharField("Kabupaten/Kota", max_length=100, blank=True)
    province = models.CharField("Provinsi", max_length=100, blank=True)
    postal_code = models.CharField("Kode pos", max_length=10, blank=True)
    phone = models.CharField("Telepon", max_length=30, blank=True)
    email = models.EmailField("Email", blank=True)
    website = models.URLField("Website", blank=True)
    leader_name = models.CharField("Nama pimpinan", max_length=150, blank=True)
    leader_rank = models.CharField("Pangkat/golongan pimpinan", max_length=120, blank=True)
    leader_nip = models.CharField("NIP pimpinan", max_length=30, blank=True)
    leader_title = models.CharField("Jabatan pimpinan", max_length=120, blank=True)

    class Meta:
        verbose_name = "Konfigurasi instansi"

    def __str__(self):
        return self.work_unit or self.institution_name


class SipedeIntegration(models.Model):
    """Kredensial dan sesi SIPede terenkripsi untuk satu akun SIKAP-PU."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sipede_integration")
    username = models.CharField("Username SIPede", max_length=150)
    password_encrypted = models.TextField("Password terenkripsi")
    session_encrypted = models.TextField("Sesi terenkripsi", blank=True)
    connected_at = models.DateTimeField("Terhubung pada", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integrasi SIPede"
        verbose_name_plural = "Integrasi SIPede"

    def __str__(self):
        return f"SIPede: {self.user}"


class CMSIntegration(models.Model):
    """Konfigurasi kredensial CMS terenkripsi untuk satu akun SIKAP-PU."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cms_integration",
    )
    username = models.CharField("Username CMS", max_length=150)
    password_encrypted = models.TextField("Password terenkripsi")
    session_encrypted = models.TextField("Sesi terenkripsi", blank=True)
    connected_at = models.DateTimeField("Terhubung pada", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Integerasi CMS"
        verbose_name_plural = "Integerasi CMS"

    def __str__(self):
        return f"CMS: {self.user}"


class CMSServiceConfiguration(SingletonModel):
    base_url = models.URLField("Alamat CMS", blank=True)

    class Meta:
        verbose_name = "Konfigurasi layanan CMS"

    def __str__(self):
        return self.base_url or "Alamat CMS belum dikonfigurasi"


class LetterNumberConfiguration(SingletonModel):
    class ResetPeriod(models.TextChoices):
        NEVER = "never", "Tidak pernah"
        MONTHLY = "monthly", "Setiap bulan"
        YEARLY = "yearly", "Setiap tahun"

    format_template = models.CharField(
        "Format nomor surat", max_length=150,
        default="{nomor}/{kode}/{bulan}/{tahun}",
        help_text="Gunakan: {nomor}, {kode}, {unit}, {bulan}, dan {tahun}.",
    )
    letter_code = models.CharField("Kode surat", max_length=30, default="B")
    unit_code = models.CharField("Kode satuan kerja", max_length=30, blank=True)
    last_number = models.PositiveIntegerField("Nomor terakhir", default=0)
    number_padding = models.PositiveSmallIntegerField("Jumlah digit nomor", default=3)
    reset_period = models.CharField("Reset penomoran", max_length=10, choices=ResetPeriod.choices, default=ResetPeriod.YEARLY)
    use_roman_month = models.BooleanField("Gunakan angka Romawi untuk bulan", default=True)

    class Meta:
        verbose_name = "Konfigurasi nomor surat"

    def clean(self):
        allowed = {"nomor", "kode", "unit", "bulan", "tahun"}
        import string
        try:
            fields = {name for _, name, _, _ in string.Formatter().parse(self.format_template) if name}
        except ValueError as error:
            raise ValidationError({"format_template": "Format nomor surat tidak valid."}) from error
        invalid = fields - allowed
        if invalid:
            raise ValidationError({"format_template": f"Variabel tidak dikenal: {', '.join(sorted(invalid))}."})
        if "nomor" not in fields:
            raise ValidationError({"format_template": "Format wajib memuat {nomor}."})
        if not 1 <= self.number_padding <= 10:
            raise ValidationError({"number_padding": "Jumlah digit harus antara 1 sampai 10."})

    def preview(self):
        from django.utils import timezone
        now = timezone.localdate()
        roman = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
        values = {
            "nomor": str(self.last_number + 1).zfill(self.number_padding),
            "kode": self.letter_code,
            "unit": self.unit_code,
            "bulan": roman[now.month - 1] if self.use_roman_month else f"{now.month:02d}",
            "tahun": now.year,
        }
        try:
            return self.format_template.format(**values)
        except (KeyError, ValueError):
            return "Format belum valid"

    def __str__(self):
        return self.format_template


class IssueCode(models.Model):
    code = models.CharField("Kode masalah", max_length=30, unique=True)
    category = models.CharField("Kategori", max_length=100, blank=True)
    description = models.CharField("Uraian masalah", max_length=255)
    is_active = models.BooleanField("Aktif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        verbose_name = "Kode masalah"
        verbose_name_plural = "Kode masalah"
        ordering = ("code",)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.description}"


class LetterNumberCode(models.Model):
    directorate = models.CharField("Direktorat", max_length=80, unique=True)
    code = models.CharField("Kode surat", max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "Kode nomor surat"
        verbose_name_plural = "Kode nomor surat"
        ordering = ("id",)

    def save(self, *args, **kwargs):
        self.directorate = " ".join(self.directorate.split())
        self.code = self.code.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.directorate}: {self.code}"


class LetterNumberCaseType(models.Model):
    letter_number = models.ForeignKey(
        LetterNumberCode,
        on_delete=models.CASCADE,
        related_name="case_types",
    )
    name = models.CharField("Jenis perkara", max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Jenis perkara nomor surat"
        verbose_name_plural = "Jenis perkara nomor surat"
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("letter_number", "name"),
                name="unique_letter_number_case_type",
            )
        ]

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class InvestigatorInstitution(models.Model):
    name = models.CharField("Instansi penyidik", max_length=180, unique=True)
    is_active = models.BooleanField("Aktif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_investigator_institutions",
    )

    class Meta:
        verbose_name = "Instansi penyidik"
        verbose_name_plural = "Instansi penyidik"
        ordering = ("name",)

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class InvestigatorUnit(models.Model):
    institution = models.ForeignKey(
        InvestigatorInstitution,
        on_delete=models.CASCADE,
        related_name="units",
        verbose_name="Instansi penyidik",
    )
    name = models.CharField("Instansi pelaksana penyidik", max_length=180)
    place = models.CharField("Tempat", max_length=150, blank=True)
    is_active = models.BooleanField("Aktif", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_investigator_units",
    )

    class Meta:
        verbose_name = "Instansi pelaksana penyidik"
        verbose_name_plural = "Instansi pelaksana penyidik"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("institution", "name"),
                name="unique_investigator_unit_per_institution",
            )
        ]

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.place = " ".join(self.place.split())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DocumentLayoutConfiguration(models.Model):
    TEMPLATE_P16 = "p16"
    TEMPLATE_CHOICES = ((TEMPLATE_P16, "P-16"),)

    template_key = models.CharField("Template dokumen", max_length=30, choices=TEMPLATE_CHOICES, unique=True)
    settings = models.JSONField("Pengaturan tata letak", default=dict, blank=True)
    revision = models.PositiveIntegerField("Revisi", default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_document_layouts",
    )

    class Meta:
        verbose_name = "Tata letak dokumen"
        verbose_name_plural = "Tata letak dokumen"
        ordering = ("template_key",)

    def __str__(self):
        return self.get_template_key_display()


class DocumentTemplateConfiguration(models.Model):
    """Teks sumber yang dipakai ketika aplikasi membentuk draf baru."""

    template_key = models.CharField("Menu dokumen", max_length=30, unique=True)
    sections = models.JSONField("Template bagian dokumen", default=dict, blank=True)
    revision = models.PositiveIntegerField("Revisi", default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_document_templates",
    )

    class Meta:
        verbose_name = "Template generate dokumen"
        verbose_name_plural = "Template generate dokumen"
        ordering = ("template_key",)

    def __str__(self):
        return self.template_key
