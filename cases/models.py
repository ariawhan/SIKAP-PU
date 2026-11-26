from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def validate_pdf(value):
    if Path(value.name).suffix.lower() != ".pdf":
        raise ValidationError("Dokumen SPDP harus berupa berkas PDF.")
    if value.size > 3 * 1024 * 1024:
        raise ValidationError("Ukuran dokumen SPDP maksimal 3 MB.")


def validate_stage_one_pdf(value):
    if Path(value.name).suffix.lower() != ".pdf":
        raise ValidationError("Surat pengantar Tahap 1 harus berupa berkas PDF.")
    if value.size > 10 * 1024 * 1024:
        raise ValidationError("Ukuran surat pengantar Tahap 1 maksimal 10 MB.")


class SPDP(models.Model):
    class LegalSubject(models.TextChoices):
        ADULT = "dewasa", "Dewasa"
        CHILD = "anak", "Anak"
        CORPORATION = "korporasi", "Korporasi"

    class Status(models.TextChoices):
        RECEIVED = "diterima", "Diterima"
        PROCESS = "proses", "Dalam Proses"
        RETURNED = "dikembalikan", "Dikembalikan"

    origin = models.CharField("Asal surat", max_length=50, blank=True, default="")
    directorate = models.CharField("Direktorat", max_length=150, default="")
    investigator_agency = models.CharField("Instansi penyidik", max_length=250)
    investigating_unit = models.CharField("Instansi pelaksana penyidik", max_length=250)
    investigation_order_number = models.CharField("Nomor Sprindik", max_length=200)
    investigation_order_date = models.DateField("Tanggal Sprindik")
    letter_number = models.CharField("Nomor SPDP", max_length=200, unique=True)
    letter_date = models.DateField("Tanggal SPDP")
    received_date = models.DateField("Tanggal diterima")
    work_area = models.CharField("Wilayah kerja", max_length=180, blank=True)
    incident_at = models.DateTimeField("Waktu kejadian perkara", null=True, blank=True)
    incident_place = models.TextField("Tempat kejadian", blank=True)
    legal_subject = models.CharField("Subjek hukum", max_length=20, choices=LegalSubject.choices, default=LegalSubject.ADULT)
    case_summary = models.TextField("Uraian singkat perkara")
    laws_and_articles = models.TextField("Undang-undang dan pasal")
    criminal_code = models.CharField("Kode pidana", max_length=30, blank=True)
    case_type = models.CharField("Jenis perkara", max_length=150, default="")
    is_high_priority = models.BooleanField("PK-Ting", default=False)
    document = models.FileField("Dokumen SPDP", upload_to="spdp/%Y/%m/", validators=[validate_pdf], blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_spdp")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-received_date", "-created_at")
        verbose_name = "SPDP"
        verbose_name_plural = "SPDP"

    def clean(self):
        errors = {}
        if self.investigation_order_date and self.letter_date and self.investigation_order_date > self.letter_date:
            errors["investigation_order_date"] = "Tanggal Sprindik tidak boleh setelah tanggal SPDP."
        if self.letter_date and self.received_date and self.received_date < self.letter_date:
            errors["received_date"] = "Tanggal diterima tidak boleh sebelum tanggal SPDP."
        if self.incident_at and self.letter_date and self.incident_at.date() > self.letter_date:
            errors["incident_at"] = "Waktu kejadian tidak boleh setelah tanggal SPDP."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.letter_number


class Suspect(models.Model):
    class SuspectType(models.TextChoices):
        SUSPECT = "TERSANGKA", "Tersangka"
        REPORTED = "TERLAPOR", "Terlapor"
        CORPORATION = "KORPORASI", "Korporasi"
        CORPORATE_BOARD = "PENGURUS KORPORASI", "Pengurus Korporasi"

    class Gender(models.TextChoices):
        MALE = "L", "Laki-laki"
        FEMALE = "P", "Perempuan"

    spdp = models.ForeignKey(SPDP, on_delete=models.CASCADE, related_name="suspects")
    sequence = models.PositiveSmallIntegerField("Urutan", default=1)
    decree_number = models.CharField("No Penetapan", max_length=120, blank=True)
    decree_date = models.DateField("Tgl Penetapan", null=True, blank=True)
    suspect_type = models.CharField("Jenis tersangka", max_length=30, choices=SuspectType.choices, blank=True)
    corporate_position = models.CharField("Jabatan", max_length=150, blank=True)
    name = models.CharField("Nama lengkap", max_length=180)
    alias = models.CharField("Alias", max_length=120, blank=True)
    front_title = models.CharField("Gelar depan", max_length=30, blank=True)
    back_title = models.CharField("Gelar belakang", max_length=30, blank=True)
    birth_place = models.CharField("Tempat lahir", max_length=100, blank=True)
    birth_date = models.DateField("Tanggal lahir", null=True, blank=True)
    age = models.PositiveSmallIntegerField("Umur", null=True, blank=True)
    ethnicity = models.CharField("Suku", max_length=80, blank=True)
    gender = models.CharField("Jenis kelamin", max_length=1, choices=Gender.choices, blank=True)
    marital_status = models.CharField("Status nikah", max_length=50, blank=True)
    identity_type = models.CharField("Jenis identitas", max_length=30, blank=True)
    identity_number = models.CharField("Nomor identitas", max_length=50, blank=True)
    phone = models.CharField("Nomor HP", max_length=30, blank=True)
    address = models.TextField("Alamat", blank=True)
    religion = models.CharField("Agama", max_length=30, blank=True)
    nationality = models.CharField("Kewarganegaraan", max_length=60, default="Indonesia", blank=True)
    occupation = models.CharField("Pekerjaan", max_length=100, blank=True)
    occupation_other = models.CharField("Pekerjaan lainnya", max_length=150, blank=True)
    education = models.CharField("Pendidikan", max_length=60, blank=True)
    disability_types = models.CharField("Disabilitas", max_length=180, blank=True)
    father_name = models.CharField("Nama ayah", max_length=150, blank=True)
    mother_name = models.CharField("Nama ibu", max_length=150, blank=True)
    corporation_deed_number = models.CharField("Nomor AD/Akta Pendirian/Perubahan Terakhir", max_length=200, blank=True)
    corporation_founding_decision_number = models.CharField("No. Salinan Keputusan Menkumham (Pendirian)", max_length=200, blank=True)
    corporation_change_decision_number = models.CharField("No. Salinan Keputusan Menkumham (Perubahan)", max_length=200, blank=True)
    corporation_crime_deed_number = models.CharField("No. Akta Saat Tindak Pidana Terjadi", max_length=200, blank=True)
    corporation_crime_deed_date = models.DateField("Tgl. Akta Saat Tindak Pidana Terjadi", null=True, blank=True)
    corporation_home_affairs_number = models.CharField("SK Terdaftar Mendagri (Ormas)", max_length=200, blank=True)
    corporation_business_type = models.CharField("Bentuk Kegiatan/Usaha", max_length=200, blank=True)
    corporation_tax_number = models.CharField("NPWP Korporasi", max_length=80, blank=True)
    corporation_registration_number = models.CharField("No. Wajib Daftar Perusahaan", max_length=120, blank=True)
    corporation_other_identity = models.TextField("Identitas Lainnya", blank=True)

    class Meta:
        ordering = ("sequence", "id")
        verbose_name = "Tersangka"
        constraints = [models.UniqueConstraint(fields=("spdp", "sequence"), name="unique_suspect_sequence_per_spdp")]

    @staticmethod
    def calculate_age(birth_date, on_date=None):
        if not birth_date:
            return None
        on_date = on_date or timezone.localdate()
        age = on_date.year - birth_date.year - ((on_date.month, on_date.day) < (birth_date.month, birth_date.day))
        return age if age >= 0 else None

    def save(self, *args, **kwargs):
        self.age = self.calculate_age(self.birth_date)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Victim(models.Model):
    class Gender(models.TextChoices):
        MALE = "L", "Laki-laki"
        FEMALE = "P", "Perempuan"

    spdp = models.ForeignKey(SPDP, on_delete=models.CASCADE, related_name="victims")
    sequence = models.PositiveSmallIntegerField("Urutan", default=1)
    name = models.CharField("Nama lengkap", max_length=180)
    alias = models.CharField("Alias", max_length=120, blank=True)
    front_title = models.CharField("Gelar depan", max_length=30, blank=True)
    back_title = models.CharField("Gelar belakang", max_length=30, blank=True)
    father_name = models.CharField("Nama ayah", max_length=150, blank=True)
    mother_name = models.CharField("Nama ibu", max_length=150, blank=True)
    birth_place = models.CharField("Tempat lahir", max_length=100, blank=True)
    birth_date = models.DateField("Tanggal lahir", null=True, blank=True)
    nationality = models.CharField("Kewarganegaraan", max_length=60, default="Indonesia", blank=True)
    ethnicity = models.CharField("Suku", max_length=80, blank=True)
    identity_type = models.CharField("Identitas", max_length=30, blank=True)
    identity_number = models.CharField("No identitas", max_length=50, blank=True)
    gender = models.CharField("Jenis kelamin", max_length=1, choices=Gender.choices, blank=True)
    marital_status = models.CharField("Status nikah", max_length=50, blank=True)
    address = models.TextField("Alamat", blank=True)
    religion = models.CharField("Agama", max_length=30, blank=True)
    phone = models.CharField("No HP", max_length=30, blank=True)
    education = models.CharField("Pendidikan", max_length=60, blank=True)
    occupation = models.CharField("Pekerjaan", max_length=100, blank=True)
    relationship = models.CharField("Hubungan korban", max_length=50, blank=True)
    occupation_other = models.CharField("Pekerjaan lainnya", max_length=150, blank=True)
    disability_types = models.CharField("Disabilitas", max_length=180, blank=True)

    class Meta:
        ordering = ("sequence", "id")
        verbose_name = "Korban"
        constraints = [models.UniqueConstraint(fields=("spdp", "sequence"), name="unique_victim_sequence_per_spdp")]

    def __str__(self):
        return self.name


class Receipt(models.Model):
    class ReceiptType(models.TextChoices):
        INVESTIGATION_RESULT = "hasil_penyidikan", "Hasil Penyidikan"
        ADDITIONAL_INVESTIGATION_RESULT = "hasil_penyidikan_tambahan", "Hasil Penyidikan Tambahan"
        CASE_EXPOSE_FOLLOWUP = "tindak_lanjut_gelar_perkara", "Sebagai Tindak Lanjut Hasil Gelar Perkara Bersama"

    spdp = models.ForeignKey(SPDP, on_delete=models.CASCADE, related_name="receipts")
    sequence = models.PositiveSmallIntegerField("Urutan", default=1)
    receipt_type = models.CharField("Jenis", max_length=40, choices=ReceiptType.choices, default=ReceiptType.INVESTIGATION_RESULT, blank=True)
    cover_letter_number = models.CharField("Nomor pengantar", max_length=150, blank=True)
    cover_letter_date = models.DateField("Tanggal pengantar", null=True, blank=True)
    received_at = models.DateTimeField("Tanggal diterima", null=True, blank=True)
    issued_date = models.DateField("Tanggal dikeluarkan", null=True, blank=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spdp_receipts",
        verbose_name="Nama penerima",
    )
    recipient_name = models.CharField("Nama penerima", max_length=180, blank=True)
    recipient_rank = models.CharField("Pangkat penerima", max_length=120, blank=True)
    recipient_position = models.CharField("Jabatan penerima", max_length=160, blank=True)
    recipient_nip = models.CharField("NIP penerima", max_length=30, blank=True)
    investigator_name = models.CharField("Nama penyidik", max_length=180, blank=True)
    investigator_nrp = models.CharField("NRP penyidik", max_length=80, blank=True)
    investigator_rank = models.CharField("Pangkat penyidik", max_length=120, blank=True)
    investigator_position = models.CharField("Jabatan penyidik", max_length=160, blank=True)

    class Meta:
        ordering = ("sequence", "id")
        verbose_name = "Tanda Terima"
        constraints = [models.UniqueConstraint(fields=("spdp", "sequence"), name="unique_receipt_sequence_per_spdp")]

    def __str__(self):
        return f"{self.get_receipt_type_display()} - {self.spdp.letter_number}"


class CaseInvestigator(models.Model):
    spdp = models.ForeignKey(
        SPDP, on_delete=models.CASCADE, related_name="investigators",
        verbose_name="Perkara / SPDP",
    )
    sequence = models.PositiveSmallIntegerField("Urutan", default=1)
    name = models.CharField("Nama penyidik", max_length=180)
    phone = models.CharField("Nomor HP", max_length=30)

    class Meta:
        ordering = ("sequence", "id")
        verbose_name = "Penyidik Perkara"
        verbose_name_plural = "Penyidik Perkara"
        constraints = [
            models.UniqueConstraint(
                fields=("spdp", "sequence"),
                name="unique_case_investigator_sequence_per_spdp",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.spdp.letter_number}"


class StageOne(models.Model):
    spdp = models.OneToOneField(
        SPDP, on_delete=models.CASCADE, related_name="stage_one", verbose_name="Perkara",
    )
    case_file_number = models.CharField("Nomor berkas perkara", max_length=200)
    cover_letter_number = models.CharField("Nomor surat pengantar", max_length=200)
    laws_and_articles = models.TextField("Undang-undang dan pasal dalam berkas perkara")
    cover_letter_document = models.FileField(
        "Surat pengantar", upload_to="stage-one/cover-letters/%Y/%m/",
        validators=[validate_stage_one_pdf],
    )
    completed_at = models.DateTimeField("Tahap 1 diselesaikan", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_stage_one_records", verbose_name="Dibuat oleh",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="updated_stage_one_records", verbose_name="Diperbarui oleh",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-completed_at", "-id")
        verbose_name = "Tahap 1"
        verbose_name_plural = "Tahap 1"

    def __str__(self):
        return f"Tahap 1 - {self.spdp.letter_number}"


class P16Assignment(models.Model):
    class Status(models.TextChoices):
        WAITING_PROSECUTOR = "menunggu_jaksa", "Menunggu Penunjukan Jaksa"
        ASSIGNED = "jaksa_ditunjuk", "Jaksa Ditunjuk"

    spdp = models.OneToOneField(SPDP, on_delete=models.CASCADE, related_name="p16_assignment")
    kasi_pidum = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="p16_as_kasi",
        verbose_name="Kasi Pidum",
    )
    prosecutors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="p16_as_prosecutor", blank=True,
        verbose_name="Jaksa",
    )
    appointed_prosecutors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="p16_as_appointed_prosecutor", blank=True,
        verbose_name="Jaksa yang ditunjuk awal",
    )
    administrative_staff = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="p16_as_administrative_staff", blank=True,
        verbose_name="Petugas administrasi",
    )
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.WAITING_PROSECUTOR)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="started_p16", verbose_name="Diproses oleh",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Penunjukan P-16"
        verbose_name_plural = "Penunjukan P-16"

    def __str__(self):
        return f"P-16 {self.spdp.letter_number}"


class P16Draft(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draf"

    class SipedeStatus(models.TextChoices):
        PENDING = "belum", "Belum diunggah"
        UPLOADED = "sudah", "Sudah diunggah"

    class ActingType(models.TextChoices):
        PLT = "plt", "Plt."
        PLH = "plh", "Plh."

    assignment = models.OneToOneField(P16Assignment, on_delete=models.CASCADE, related_name="draft", verbose_name="Penunjukan P-16")
    draft_number = models.CharField("Nomor draf", max_length=100, unique=True)
    manual_number = models.BooleanField("Isi nomor surat secara manual", default=False)
    letter_date = models.DateField("Tanggal surat")
    acting_type = models.CharField(
        "Status pelaksana", max_length=3, choices=ActingType.choices, blank=True,
    )
    acting_name = models.CharField("Nama pejabat pelaksana", max_length=150, blank=True)
    acting_position = models.CharField("Jabatan/Pangkat pejabat pelaksana", max_length=150, blank=True)
    acting_nip = models.CharField("NIP pejabat pelaksana", max_length=30, blank=True)
    subject = models.CharField("Perihal", max_length=200, default="Penunjukan Jaksa Penuntut Umum")
    consideration_html = models.TextField("Menimbang", blank=True)
    legal_basis_html = models.TextField("Dasar", blank=True)
    offense_summary_html = models.TextField("Uraian tindak pidana", blank=True)
    recipient_html = models.TextField("Kepada", blank=True)
    instruction_html = models.TextField("Untuk", blank=True)
    copies_html = models.TextField("Tembusan", blank=True)
    administration_legal_basis_html = models.TextField("Dasar petugas administrasi", blank=True)
    administration_consideration_html = models.TextField("Pertimbangan petugas administrasi", blank=True)
    administration_instruction_html = models.TextField("Untuk petugas administrasi", blank=True)
    administration_copies_html = models.TextField("Tembusan petugas administrasi", blank=True)
    barcode_image = models.ImageField(
        "Barcode/QR",
        upload_to="p16/barcodes/%Y/%m/",
        blank=True,
        null=True,
    )
    signatory = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="signed_p16_drafts",
        verbose_name="Penanda tangan",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    sipede_status = models.CharField(
        "Status SIPede", max_length=10, choices=SipedeStatus.choices,
        default=SipedeStatus.PENDING,
    )
    sipede_uploaded_at = models.DateTimeField("Diunggah ke SIPede", null=True, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="generated_p16_drafts", verbose_name="Dibuat oleh")
    content_html = models.TextField("Isi dokumen", blank=True)
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="edited_p16_drafts", verbose_name="Terakhir diedit oleh",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Draf P-16"
        verbose_name_plural = "Draf P-16"

    @classmethod
    def create_for_assignment(cls, assignment, user):
        today = timezone.localdate()
        if assignment.prosecutors.exists() and not assignment.appointed_prosecutors.exists():
            assignment.appointed_prosecutors.set(assignment.prosecutors.all())
        draft, created = cls.objects.get_or_create(
            assignment=assignment,
            defaults={"draft_number": f"DRAFT/P-16/{assignment.pk:04d}/{today.year}", "letter_date": today, "generated_by": user},
        )
        from .p16_content import build_default_p16_content, ensure_p16_sections
        ensure_p16_sections(draft)
        if not draft.content_html:
            draft.content_html = build_default_p16_content(draft)
            draft.save(update_fields=("content_html", "updated_at"))
        return draft, created

    def __str__(self):
        return self.draft_number

    @property
    def is_issued(self):
        return bool(self.draft_number and not self.draft_number.startswith("DRAFT/"))


class ActingSignatoryDraft(models.Model):
    ACTING_TYPE_CHOICES = (("plt", "Plt."), ("plh", "Plh."))

    acting_type = models.CharField(
        "Status pelaksana", max_length=3, choices=ACTING_TYPE_CHOICES, blank=True,
    )
    acting_name = models.CharField("Nama pejabat pelaksana", max_length=150, blank=True)
    acting_position = models.CharField("Jabatan/Pangkat pejabat pelaksana", max_length=150, blank=True)
    acting_nip = models.CharField("NIP pejabat pelaksana", max_length=30, blank=True)

    class Meta:
        abstract = True


class P17Draft(ActingSignatoryDraft):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draf"

    class SipedeStatus(models.TextChoices):
        NOT_UPLOADED = "belum", "Belum diunggah"
        UPLOADED = "sudah", "Sudah diunggah"

    spdp = models.ForeignKey(SPDP, on_delete=models.CASCADE, related_name="p17_drafts", verbose_name="SPDP")
    sequence = models.PositiveSmallIntegerField("Permintaan ke", default=1)
    letter_number = models.CharField("Nomor surat", max_length=120, unique=True)
    manual_number = models.BooleanField("Isi nomor surat secara manual", default=False)
    letter_date = models.DateField("Tanggal surat")
    letter_nature = models.CharField("Sifat", max_length=50, default="Biasa")
    attachment = models.CharField("Lampiran", max_length=100, default="-")
    subject_html = models.TextField("Hal", blank=True)
    recipient_html = models.TextField("Kepada Yth", blank=True)
    body_html = models.TextField("Isi", blank=True)
    copies_html = models.TextField("Tembusan", blank=True)
    barcode_image = models.ImageField(
        "Barcode/QR",
        upload_to="p17/barcodes/%Y/%m/",
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    sipede_status = models.CharField(
        max_length=10, choices=SipedeStatus.choices, default=SipedeStatus.NOT_UPLOADED,
    )
    sipede_uploaded_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_p17_drafts", verbose_name="Dibuat oleh",
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="edited_p17_drafts", verbose_name="Terakhir diedit oleh",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Draf P-17"
        verbose_name_plural = "Draf P-17"
        constraints = [
            models.UniqueConstraint(fields=("spdp", "sequence"), name="unique_p17_sequence_per_spdp"),
        ]

    @classmethod
    def create_for_spdp(cls, spdp, user):
        today = timezone.localdate()
        sequence = (spdp.p17_drafts.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        draft = cls.objects.create(
            spdp=spdp,
            sequence=sequence,
            letter_number=f"DRAFT/P-17/{spdp.pk:04d}/{sequence:02d}/{today.year}",
            letter_date=today,
            created_by=user,
        )
        from .p17_content import ensure_p17_sections
        ensure_p17_sections(draft)
        return draft

    def __str__(self):
        return self.letter_number


class SOPForm1BDraft(models.Model):
    p17_draft = models.OneToOneField(
        P17Draft,
        on_delete=models.CASCADE,
        related_name="sop_form_1b",
        verbose_name="Draf P-17",
    )
    report_date = models.DateField("Tanggal laporan", default=timezone.localdate)
    recipient = models.CharField("Kepada Yth.", max_length=300)
    sender = models.TextField("Dari")
    attachment = models.CharField("Lampiran", max_length=100, default="1 (satu) berkas")
    subject = models.TextField("Perihal")
    legal_basis_html = models.TextField("Dasar", blank=True)
    facts_html = models.TextField("Fakta dan data", blank=True)
    legal_analysis_html = models.TextField("Analisis yuridis", blank=True)
    conclusion_html = models.TextField("Kesimpulan dan saran", blank=True)
    closing = models.TextField(
        "Penutup",
        default="Demikian untuk menjadi periksa dan mohon petunjuk.",
    )
    prosecutor_name = models.CharField("Nama Penuntut Umum", max_length=180, blank=True)
    prosecutor_rank = models.CharField("Pangkat Penuntut Umum", max_length=120, blank=True)
    prosecutor_nip = models.CharField("NIP Penuntut Umum", max_length=30, blank=True)
    kasi_opinion_html = models.TextField("Pendapat Kasipidum", blank=True)
    leader_instruction_html = models.TextField("Petunjuk Kajari", blank=True)
    barcode_image = models.ImageField(
        "Barcode/QR", upload_to="sop-form-1b/barcodes/%Y/%m/", blank=True, null=True,
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="edited_sop_form_1b_drafts",
        verbose_name="Terakhir diedit oleh",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Draf SOP Form-1B"
        verbose_name_plural = "Draf SOP Form-1B"

    def __str__(self):
        return f"SOP Form-1B - {self.p17_draft.letter_number}"


class P21Draft(ActingSignatoryDraft):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draf"
        COMPLETED = "completed", "Sudah P-21"

    class SipedeStatus(models.TextChoices):
        NOT_UPLOADED = "belum", "Belum diunggah"
        UPLOADED = "sudah", "Sudah diunggah"

    spdp = models.OneToOneField(
        SPDP, on_delete=models.CASCADE, related_name="p21_draft", verbose_name="SPDP",
    )
    letter_number = models.CharField("Nomor surat", max_length=120, unique=True)
    manual_number = models.BooleanField("Isi nomor surat secara manual", default=False)
    letter_date = models.DateField("Tanggal surat")
    letter_nature = models.CharField("Sifat", max_length=50, default="Rahasia")
    attachment = models.CharField("Lampiran", max_length=100, default="1 (satu) Berkas")
    subject_html = models.TextField("Hal", blank=True)
    recipient_html = models.TextField("Kepada Yth", blank=True)
    legal_basis_html = models.TextField("Dasar", blank=True)
    body_html = models.TextField("Isi", blank=True)
    copies_html = models.TextField("Tembusan", blank=True)
    barcode_image = models.ImageField("Barcode/QR", upload_to="p21/barcodes/%Y/%m/", blank=True, null=True)
    sipede_status = models.CharField(max_length=10, choices=SipedeStatus.choices, default=SipedeStatus.NOT_UPLOADED)
    sipede_uploaded_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_p21_drafts", verbose_name="Dibuat oleh",
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="edited_p21_drafts", verbose_name="Terakhir diedit oleh",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Draf P-21"
        verbose_name_plural = "Draf P-21"

    @classmethod
    def create_for_spdp(cls, spdp, user):
        today = timezone.localdate()
        draft = cls.objects.create(
            spdp=spdp,
            letter_number=f"DRAFT/P-21/{spdp.pk:04d}/{today.year}",
            letter_date=today,
            created_by=user,
        )
        from .p21_content import ensure_p21_sections
        ensure_p21_sections(draft)
        return draft

    def __str__(self):
        return self.letter_number


class SOPForm02Draft(ActingSignatoryDraft):
    class SipedeStatus(models.TextChoices):
        NOT_UPLOADED = "belum", "Belum diunggah"
        UPLOADED = "sudah", "Sudah diunggah"

    spdp = models.OneToOneField(SPDP, on_delete=models.CASCADE, related_name="sop_form_02_draft", verbose_name="SPDP")
    letter_number = models.CharField("Nomor surat", max_length=120, unique=True)
    manual_number = models.BooleanField("Isi nomor surat secara manual", default=False)
    letter_date = models.DateField("Tanggal surat")
    letter_nature = models.CharField("Sifat", max_length=50, default="Biasa")
    attachment = models.CharField("Lampiran", max_length=100, default="-")
    subject_html = models.TextField("Hal", blank=True)
    recipient_html = models.TextField("Kepada Yth", blank=True)
    body_html = models.TextField("Isi", blank=True)
    copies_html = models.TextField("Tembusan", blank=True)
    barcode_image = models.ImageField("Barcode/QR", upload_to="sop-forms/barcodes/%Y/%m/", blank=True, null=True)
    sipede_status = models.CharField(max_length=10, choices=SipedeStatus.choices, default=SipedeStatus.NOT_UPLOADED)
    sipede_uploaded_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=(("draft", "Draf"),), default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_sop_form_02_drafts")
    last_edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="edited_sop_form_02_drafts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Draf SOP Form 2"
        verbose_name_plural = "Draf SOP Form 2"

    @classmethod
    def create_for_spdp(cls, spdp, user):
        today = timezone.localdate()
        draft = cls.objects.create(spdp=spdp, letter_number=f"DRAFT/SOP-02/{spdp.pk:04d}/{today.year}", letter_date=today, created_by=user)
        from .sop_form_content import ensure_sop_form_02_sections
        ensure_sop_form_02_sections(draft)
        return draft

    def __str__(self):
        return self.letter_number


class SOPForm03Draft(ActingSignatoryDraft):
    class SipedeStatus(models.TextChoices):
        NOT_UPLOADED = "belum", "Belum diunggah"
        UPLOADED = "sudah", "Sudah diunggah"

    spdp = models.OneToOneField(SPDP, on_delete=models.CASCADE, related_name="sop_form_03_draft", verbose_name="SPDP")
    letter_number = models.CharField("Nomor surat", max_length=120, unique=True)
    manual_number = models.BooleanField("Isi nomor surat secara manual", default=False)
    letter_date = models.DateField("Tanggal surat")
    letter_nature = models.CharField("Sifat", max_length=50, default="Biasa")
    attachment = models.CharField("Lampiran", max_length=100, default="-")
    subject_html = models.TextField("Hal", blank=True)
    recipient_html = models.TextField("Kepada Yth", blank=True)
    body_html = models.TextField("Isi", blank=True)
    copies_html = models.TextField("Tembusan", blank=True)
    barcode_image = models.ImageField("Barcode/QR", upload_to="sop-forms/barcodes/%Y/%m/", blank=True, null=True)
    sipede_status = models.CharField(max_length=10, choices=SipedeStatus.choices, default=SipedeStatus.NOT_UPLOADED)
    sipede_uploaded_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=(("draft", "Draf"),), default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_sop_form_03_drafts")
    last_edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="edited_sop_form_03_drafts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Draf SOP Form 3"
        verbose_name_plural = "Draf SOP Form 3"

    @classmethod
    def create_for_spdp(cls, spdp, user):
        today = timezone.localdate()
        draft = cls.objects.create(spdp=spdp, letter_number=f"DRAFT/SOP-03/{spdp.pk:04d}/{today.year}", letter_date=today, created_by=user)
        from .sop_form_content import ensure_sop_form_03_sections
        ensure_sop_form_03_sections(draft)
        return draft

    def __str__(self):
        return self.letter_number


class CaseDocumentDraft(ActingSignatoryDraft):
    class DocumentType(models.TextChoices):
        P18 = "p18", "P-18"
        P19 = "p19", "P-19"
        P20 = "p20", "P-20"
        SOP_FORM_07 = "sop07", "SOP Form 7"

    class SipedeStatus(models.TextChoices):
        NOT_UPLOADED = "belum", "Belum diunggah"
        UPLOADED = "sudah", "Sudah diunggah"

    spdp = models.ForeignKey(SPDP, on_delete=models.CASCADE, related_name="case_document_drafts", verbose_name="SPDP")
    document_type = models.CharField("Jenis dokumen", max_length=10, choices=DocumentType.choices)
    letter_number = models.CharField("Nomor surat", max_length=120, unique=True)
    manual_number = models.BooleanField("Isi nomor surat secara manual", default=False)
    letter_date = models.DateField("Tanggal surat")
    letter_nature = models.CharField("Sifat", max_length=50, default="Biasa")
    attachment = models.CharField("Lampiran", max_length=150, default="-")
    subject_html = models.TextField("Hal", blank=True)
    recipient_html = models.TextField("Kepada Yth", blank=True)
    legal_basis_html = models.TextField("Dasar", blank=True)
    body_html = models.TextField("Isi", blank=True)
    copies_html = models.TextField("Tembusan", blank=True)
    barcode_image = models.ImageField(
        "Barcode/QR", upload_to="case-documents/barcodes/%Y/%m/", blank=True, null=True,
    )
    sipede_status = models.CharField(max_length=10, choices=SipedeStatus.choices, default=SipedeStatus.NOT_UPLOADED)
    sipede_uploaded_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=(("draft", "Draf"),), default="draft")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_case_document_drafts")
    last_edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="edited_case_document_drafts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Draf dokumen perkara"
        verbose_name_plural = "Draf dokumen perkara"
        constraints = [models.UniqueConstraint(fields=("spdp", "document_type"), name="unique_case_document_type_per_spdp")]

    @classmethod
    def create_for_spdp(cls, spdp, document_type, user):
        today = timezone.localdate()
        code = dict(cls.DocumentType.choices)[document_type].replace(" ", "-")
        draft = cls.objects.create(spdp=spdp, document_type=document_type, letter_number=f"DRAFT/{code}/{spdp.pk:04d}/{today.year}", letter_date=today, created_by=user)
        if document_type == cls.DocumentType.SOP_FORM_07:
            draft.attachment = "2 (dua) berkas (SPDP Asli dan Berkas Perkara Asli)"
            draft.save(update_fields=("attachment", "updated_at"))
        from .case_document_content import ensure_case_document_sections
        ensure_case_document_sections(draft)
        return draft

    def __str__(self):
        return self.letter_number


class CoordinationMinutesDraft(models.Model):
    class CoordinationType(models.TextChoices):
        FIRST = "ba1", "BA Koordinasi I"
        SECOND = "ba2", "BA Koordinasi II"
        THIRD = "ba3", "BA Koordinasi III"

    spdp = models.ForeignKey(
        SPDP, on_delete=models.CASCADE, related_name="coordination_minutes_drafts", verbose_name="SPDP",
    )
    coordination_type = models.CharField("Jenis koordinasi", max_length=3, choices=CoordinationType.choices)
    draft_number = models.CharField("Nomor draf", max_length=120, unique=True)
    meeting_date = models.DateField("Tanggal koordinasi")
    meeting_place = models.CharField("Tempat koordinasi", max_length=250)
    prosecutor_name = models.CharField("Nama Penuntut Umum", max_length=200, blank=True)
    prosecutor_rank = models.CharField("Pangkat Penuntut Umum", max_length=150, blank=True)
    prosecutor_nip = models.CharField("NIP Penuntut Umum", max_length=40, blank=True)
    investigator_name = models.CharField("Nama Penyidik", max_length=200, blank=True)
    investigator_rank = models.CharField("Pangkat Penyidik", max_length=150, blank=True)
    investigator_nrp = models.CharField("NRP Penyidik", max_length=40, blank=True)
    investigator_position = models.CharField("Jabatan Penyidik", max_length=150, default="Penyidik")
    investigator_supervisor_title = models.CharField("Jabatan Atasan Penyidik", max_length=200, blank=True)
    investigator_supervisor_name = models.CharField("Nama Atasan Penyidik", max_length=200, blank=True)
    investigator_supervisor_rank = models.CharField("Pangkat Atasan Penyidik", max_length=150, blank=True)
    investigator_supervisor_nrp = models.CharField("NRP Atasan Penyidik", max_length=40, blank=True)
    prosecutor_supervisor_title = models.CharField(
        "Jabatan Atasan Penuntut Umum", max_length=200, default="Kepala Seksi Tindak Pidana Umum",
    )
    prosecutor_supervisor_name = models.CharField("Nama Atasan Penuntut Umum", max_length=200, blank=True)
    prosecutor_supervisor_rank = models.CharField("Pangkat Atasan Penuntut Umum", max_length=150, blank=True)
    prosecutor_supervisor_nip = models.CharField("NIP Atasan Penuntut Umum", max_length=40, blank=True)
    body_html = models.TextField("Materi koordinasi", blank=True)
    barcode_image = models.ImageField(
        "Barcode/QR", upload_to="coordination/barcodes/%Y/%m/", blank=True, null=True,
    )
    documentation_image_1 = models.ImageField("Dokumentasi 1", upload_to="coordination/%Y/%m/", blank=True, null=True)
    documentation_image_2 = models.ImageField("Dokumentasi 2", upload_to="coordination/%Y/%m/", blank=True, null=True)
    documentation_image_3 = models.ImageField("Dokumentasi 3", upload_to="coordination/%Y/%m/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=(("draft", "Draf"),), default="draft")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_coordination_minutes_drafts",
    )
    last_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="edited_coordination_minutes_drafts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-meeting_date", "-id")
        verbose_name = "Draf BA Koordinasi"
        verbose_name_plural = "Draf BA Koordinasi"
        constraints = [
            models.UniqueConstraint(
                fields=("spdp", "coordination_type"), name="unique_coordination_type_per_spdp",
            ),
        ]

    @classmethod
    def create_for_spdp(cls, spdp, coordination_type, user):
        today = timezone.localdate()
        assignment = getattr(spdp, "p16_assignment", None)
        prosecutor = None
        kasi = None
        if assignment:
            prosecutor = assignment.appointed_prosecutors.order_by("id").first() or assignment.prosecutors.order_by("id").first()
            kasi = assignment.kasi_pidum
        draft = cls.objects.create(
            spdp=spdp,
            coordination_type=coordination_type,
            draft_number=f"DRAFT/{coordination_type.upper()}/{spdp.pk:04d}/{today.year}",
            meeting_date=today,
            meeting_place=f"Kantor {spdp.work_area}" if spdp.work_area else "Kantor Kejaksaan Negeri",
            prosecutor_name=prosecutor.display_name if prosecutor else "",
            prosecutor_rank=prosecutor.rank if prosecutor else "",
            prosecutor_nip=prosecutor.nip if prosecutor else "",
            investigator_supervisor_title=f"Kepala {spdp.investigating_unit}" if spdp.investigating_unit else "",
            prosecutor_supervisor_name=kasi.display_name if kasi else "",
            prosecutor_supervisor_rank=kasi.rank if kasi else "",
            prosecutor_supervisor_nip=kasi.nip if kasi else "",
            created_by=user,
        )
        from .coordination_content import ensure_coordination_body
        ensure_coordination_body(draft)
        return draft

    @property
    def sequence(self):
        return {"ba1": 1, "ba2": 2, "ba3": 3}.get(self.coordination_type, 1)

    def __str__(self):
        return self.draft_number
