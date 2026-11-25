from datetime import date, datetime, time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from cases.models import (
    CaseDocumentDraft,
    CoordinationMinutesDraft,
    P16Assignment,
    P16Draft,
    P17Draft,
    P21Draft,
    Receipt,
    SOPForm02Draft,
    SOPForm03Draft,
    SOPForm1BDraft,
    SPDP,
    StageOne,
    Suspect,
    Victim,
)
from configurations.models import (
    InstitutionConfiguration,
    InvestigatorInstitution,
    InvestigatorUnit,
    LetterNumberCode,
)


CASE_PROFILES = (
    ("Pencurian", "476 UU Nomor 1 Tahun 2023", "pengambilan sepeda motor yang diparkir di area permukiman"),
    ("Penipuan", "492 UU Nomor 1 Tahun 2023", "penawaran barang melalui transaksi daring yang tidak dipenuhi"),
    ("Penggelapan", "486 UU Nomor 1 Tahun 2023", "penguasaan dana titipan yang tidak dikembalikan"),
    ("Penganiayaan", "466 UU Nomor 1 Tahun 2023", "perselisihan yang mengakibatkan korban mengalami luka"),
    ("Narkotika", "Pasal 112 UU Nomor 35 Tahun 2009", "kepemilikan narkotika yang ditemukan dalam pemeriksaan"),
    ("Kekerasan dalam Rumah Tangga", "Pasal 44 UU Nomor 23 Tahun 2004", "dugaan kekerasan dalam lingkup rumah tangga"),
    ("Informasi dan Transaksi Elektronik", "Pasal 28 ayat (1) UU Nomor 1 Tahun 2024", "penyebaran informasi elektronik yang diduga merugikan konsumen"),
    ("Perusakan", "406 UU Nomor 1 Tahun 2023", "perusakan fasilitas milik pihak lain di lingkungan usaha"),
    ("Pencemaran Lingkungan", "Pasal 98 UU Nomor 32 Tahun 2009", "pembuangan limbah yang diduga mencemari saluran air"),
    ("Korupsi", "Pasal 2 UU Nomor 31 Tahun 1999 jo. UU Nomor 20 Tahun 2001", "dugaan penyimpangan penggunaan anggaran kegiatan"),
    ("Perlindungan Konsumen", "Pasal 62 UU Nomor 8 Tahun 1999", "peredaran barang yang tidak sesuai keterangan pada kemasan"),
    ("Ketenagakerjaan", "Pasal 185 UU Nomor 13 Tahun 2003", "dugaan pelanggaran ketentuan perlindungan hak pekerja"),
)

FIRST_NAMES = (
    "Aditya", "Bagus", "Citra", "Dimas", "Eka", "Farah", "Gilang", "Hana", "Indra", "Jihan",
    "Kadek", "Laras", "Made", "Nadia", "Putra", "Ratih", "Surya", "Tari", "Wahyu", "Yuni",
)
FAMILY_NAMES = (
    "Pratama", "Wibowo", "Lestari", "Saputra", "Permata", "Mahendra", "Kusuma", "Pertiwi",
    "Ramadhan", "Santoso", "Wijaya", "Anggraini", "Darmawan", "Setiawan", "Wardani", "Nugraha",
)
COMPANY_NAMES = (
    "PT Sagara Niaga", "CV Tirta Kencana", "PT Nusa Pangan Sejahtera", "CV Cakra Mandiri",
    "PT Aruna Digital", "Koperasi Karya Bersama",
)
LOCATIONS = (
    "Kecamatan Buleleng, Kabupaten Buleleng",
    "Kecamatan Sukasada, Kabupaten Buleleng",
    "Kecamatan Mengwi, Kabupaten Badung",
    "Kecamatan Denpasar Barat, Kota Denpasar",
    "Kecamatan Tabanan, Kabupaten Tabanan",
    "Kecamatan Gianyar, Kabupaten Gianyar",
)


class Command(BaseCommand):
    help = "Mengisi 50 perkara beserta variasi alur administrasi dan dokumennya."

    def handle(self, *args, **options):
        today = timezone.localdate()
        batch_numbers = [
            f"B/{901 + index:03d}/SPDP/RES.1.24/"
            f"{(today - timedelta(days=90 - index) + timedelta(days=3)).year}"
            for index in range(50)
        ]
        existing_numbers = set(
            SPDP.objects.filter(letter_number__in=batch_numbers).values_list("letter_number", flat=True)
        )
        if existing_numbers:
            if len(existing_numbers) != len(batch_numbers):
                raise CommandError(
                    "Rentang nomor perkara sudah dipakai sebagian. Tidak ada data yang diubah."
                )
            self.stdout.write(self.style.SUCCESS("50 perkara pada rangkaian ini sudah tersedia."))
            return

        institution_config = InstitutionConfiguration.objects.first()
        letter_code = LetterNumberCode.objects.prefetch_related("case_types").first()
        investigator, unit = self._get_investigator()
        created_by = self._get_user(Role.SUPER_ADMIN) or User.objects.filter(is_active=True).order_by("id").first()
        kasi = self._get_user(Role.KASI_PIDUM)
        prosecutors = list(self._users_with_role(Role.PROSECUTOR))
        work_area = (
            institution_config.work_unit
            if institution_config and institution_config.work_unit
            else "Kejaksaan Negeri Buleleng"
        )
        directorate = letter_code.directorate if letter_code else "Direktorat Tindak Pidana Umum"

        with transaction.atomic():
            for index in range(50):
                serial = 901 + index
                incident_date = today - timedelta(days=90 - index)
                order_date = incident_date + timedelta(days=2)
                letter_date = order_date + timedelta(days=1)
                received_date = letter_date + timedelta(days=1 + index % 2)
                case_year = letter_date.year
                letter_number = f"B/{serial:03d}/SPDP/RES.1.24/{case_year}"
                spdp = SPDP.objects.create(
                    origin=investigator.name[:50],
                    directorate=directorate,
                    investigator_agency=investigator.name,
                    investigating_unit=unit.name,
                    investigation_order_number=f"SP.Sidik/{serial:03d}/RES.1.24/{case_year}",
                    investigation_order_date=order_date,
                    letter_date=letter_date,
                    received_date=received_date,
                    work_area=work_area,
                    incident_at=timezone.make_aware(
                        datetime.combine(incident_date, time(19 + index % 4, 15))
                    ),
                    incident_place=LOCATIONS[index % len(LOCATIONS)],
                    legal_subject=(
                        SPDP.LegalSubject.CHILD
                        if index % 13 == 0
                        else SPDP.LegalSubject.CORPORATION
                        if index % 11 == 0
                        else SPDP.LegalSubject.ADULT
                    ),
                    case_summary=self._case_summary(index),
                    laws_and_articles=CASE_PROFILES[index % len(CASE_PROFILES)][1],
                    case_type=CASE_PROFILES[index % len(CASE_PROFILES)][0],
                    is_high_priority=index % 8 == 0,
                    status=(
                        SPDP.Status.RECEIVED,
                        SPDP.Status.PROCESS,
                        SPDP.Status.RETURNED,
                    )[index % 3],
                    created_by=created_by,
                    letter_number=letter_number,
                )
                self._create_people(spdp, index)
                self._create_receipts(spdp, index, received_date, prosecutors)
                stage_one = self._create_stage_one(spdp, index, serial, case_year, created_by)
                assignment = self._create_assignment(spdp, index, kasi, prosecutors)
                self._create_documents(spdp, index, created_by, assignment, stage_one)

        self.stdout.write(self.style.SUCCESS("50 perkara berhasil ditambahkan."))
        self.stdout.write(
            f"Jumlah perkara dalam rangkaian ini: "
            f"{SPDP.objects.filter(letter_number__in=batch_numbers).count()}"
        )
        if not kasi:
            self.stdout.write(self.style.WARNING("Alur penunjukan jaksa dilewati karena belum ada pengguna Kasi Pidum aktif."))
        elif not prosecutors:
            self.stdout.write(self.style.WARNING("Penunjukan jaksa dilewati karena belum ada pengguna Jaksa aktif."))

    @staticmethod
    def _users_with_role(role_code):
        return User.objects.filter(is_active=True, roles__code=role_code).order_by("id")

    @classmethod
    def _get_user(cls, role_code):
        return cls._users_with_role(role_code).first()

    @staticmethod
    def _get_investigator():
        unit = (
            InvestigatorUnit.objects.filter(is_active=True, institution__is_active=True)
            .select_related("institution")
            .order_by("id")
            .first()
        )
        if unit:
            return unit.institution, unit
        investigator = InvestigatorInstitution.objects.filter(is_active=True).order_by("id").first()
        if not investigator:
            raise CommandError(
                "Belum ada instansi penyidik aktif. Tambahkan konfigurasi penyidik sebelum mengisi perkara."
            )
        raise CommandError(
            "Belum ada unit penyidik aktif. Tambahkan unit untuk instansi penyidik sebelum mengisi perkara."
        )

    @staticmethod
    def _case_summary(index):
        case_type, _, description = CASE_PROFILES[index % len(CASE_PROFILES)]
        return (
            f"Penyidik menyampaikan hasil penyidikan awal atas dugaan {case_type.lower()} "
            f"terkait {description} di {LOCATIONS[index % len(LOCATIONS)]}. "
            "Penanganan perkara dilakukan sesuai keterangan saksi dan dokumen yang diterima."
        )

    @staticmethod
    def _person_name(index):
        return f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {FAMILY_NAMES[(index // len(FIRST_NAMES)) % len(FAMILY_NAMES)]}"

    def _create_people(self, spdp, index):
        subject = spdp.legal_subject
        suspect_count = (0, 1, 2, 1, 3)[index % 5]
        for sequence in range(1, suspect_count + 1):
            is_corporation = subject == SPDP.LegalSubject.CORPORATION and sequence == 1
            is_minor = subject == SPDP.LegalSubject.CHILD
            birth_date = (
                date(2009 + index % 3, 2 + index % 10, 5 + index % 20)
                if is_minor
                else date(1980 + index % 25, 1 + index % 12, 1 + index % 27)
            )
            Suspect.objects.create(
                spdp=spdp,
                sequence=sequence,
                suspect_type=(
                    Suspect.SuspectType.CORPORATION
                    if is_corporation
                    else Suspect.SuspectType.CORPORATE_BOARD
                    if subject == SPDP.LegalSubject.CORPORATION
                    else Suspect.SuspectType.REPORTED
                    if index % 4 == 0
                    else Suspect.SuspectType.SUSPECT
                ),
                corporate_position="Direktur" if subject == SPDP.LegalSubject.CORPORATION and not is_corporation else "",
                name=(
                    COMPANY_NAMES[index % len(COMPANY_NAMES)]
                    if is_corporation
                    else self._person_name(index * 3 + sequence - 1)
                ),
                alias="" if is_corporation else FIRST_NAMES[(index + sequence) % len(FIRST_NAMES)],
                birth_place="" if is_corporation else LOCATIONS[(index + sequence) % len(LOCATIONS)].split(",")[0],
                birth_date=None if is_corporation else birth_date,
                gender="" if is_corporation else (Suspect.Gender.FEMALE if index % 2 else Suspect.Gender.MALE),
                marital_status="" if is_minor or is_corporation else ("Kawin" if index % 2 else "Belum Kawin"),
                address="" if is_corporation else LOCATIONS[(index + sequence) % len(LOCATIONS)],
                nationality="Indonesia",
                occupation="Badan usaha" if is_corporation else ("Pelajar" if is_minor else "Karyawan swasta"),
                education="" if is_corporation else ("SMP" if is_minor else "SMA / Sederajat"),
                religion="" if is_corporation else ("Hindu" if index % 2 else "Islam"),
                disability_types="" if is_corporation else (
                    "Bukan Penyandang Disabilitas" if index % 9 else "Disabilitas fisik"
                ),
                corporation_business_type="Perdagangan dan jasa" if is_corporation else "",
            )

        victim_count = 0 if index % 6 == 0 else 2 if index % 10 == 0 else 1
        for sequence in range(1, victim_count + 1):
            Victim.objects.create(
                spdp=spdp,
                sequence=sequence,
                name=self._person_name(index * 2 + 53 + sequence),
                birth_place=LOCATIONS[(index + sequence + 2) % len(LOCATIONS)].split(",")[0],
                birth_date=date(1978 + index % 35, 1 + index % 12, 1 + index % 27),
                nationality="Indonesia",
                gender=Victim.Gender.MALE if index % 2 else Victim.Gender.FEMALE,
                address=LOCATIONS[(index + sequence + 2) % len(LOCATIONS)],
                relationship="Bukan Keluarga",
                occupation="Wiraswasta" if index % 2 else "Karyawan swasta",
                religion="Hindu" if index % 2 else "Islam",
                disability_types="Bukan Penyandang Disabilitas",
            )

    @staticmethod
    def _create_receipts(spdp, index, received_date, prosecutors):
        receipt_count = 0 if index % 5 == 0 else 2 if index % 4 == 0 else 1
        receipt_types = tuple(Receipt.ReceiptType.values)
        prosecutor = prosecutors[index % len(prosecutors)] if prosecutors else None
        for sequence in range(1, receipt_count + 1):
            receipt_date = received_date + timedelta(days=7 + index % 9 + sequence * 3)
            Receipt.objects.create(
                spdp=spdp,
                sequence=sequence,
                receipt_type=receipt_types[(index + sequence - 1) % len(receipt_types)],
                cover_letter_number=f"B/TT/{901 + index:03d}/{sequence:02d}/{spdp.received_date.year}",
                cover_letter_date=receipt_date,
                received_at=timezone.make_aware(datetime.combine(receipt_date, time(9 + sequence, 30))),
                issued_date=receipt_date,
                recipient_user=prosecutor,
                recipient_name=prosecutor.display_name if prosecutor else "Petugas Penerima",
                recipient_rank=prosecutor.rank if prosecutor else "",
                recipient_position="Jaksa Penuntut Umum" if prosecutor else "Petugas Penerima",
                recipient_nip=prosecutor.nip if prosecutor else "",
                investigator_name=f"IPTU {FIRST_NAMES[(index + sequence) % len(FIRST_NAMES)]}",
                investigator_nrp=f"8205{901 + index:04d}{sequence:02d}",
                investigator_rank="IPTU",
                investigator_position="Penyidik",
            )

    @staticmethod
    def _make_cover_letter_pdf(serial, year):
        text = f"Surat pengantar berkas perkara {serial} tahun {year}"
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for number, body in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf.extend(f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
        xref_offset = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(pdf)

    def _create_stage_one(self, spdp, index, serial, year, created_by):
        if index % 3 != 0 or index % 4 == 0:
            return None
        return StageOne.objects.create(
            spdp=spdp,
            case_file_number=f"BP/{serial:03d}/RES.1.24/{year}",
            cover_letter_number=f"B/{serial:03d}/RES.1.24/{year}",
            laws_and_articles=spdp.laws_and_articles,
            cover_letter_document=ContentFile(
                self._make_cover_letter_pdf(serial, year),
                name=f"Berkas_{serial:03d}_{year}.pdf",
            ),
            created_by=created_by,
        )

    @staticmethod
    def _create_assignment(spdp, index, kasi, prosecutors):
        if not kasi or spdp.status == SPDP.Status.RETURNED or index % 4 == 0:
            return None
        assigned = bool(prosecutors) and index % 3 != 1
        assignment = P16Assignment.objects.create(
            spdp=spdp,
            kasi_pidum=kasi,
            started_by=kasi,
            status=P16Assignment.Status.ASSIGNED if assigned else P16Assignment.Status.WAITING_PROSECUTOR,
            assigned_at=timezone.now() if assigned else None,
        )
        spdp.status = SPDP.Status.PROCESS
        spdp.save(update_fields=("status", "updated_at"))
        if assigned:
            prosecutor = prosecutors[index % len(prosecutors)]
            assignment.prosecutors.set([prosecutor])
            assignment.appointed_prosecutors.set([prosecutor])
            assignment.administrative_staff.set(
                User.objects.filter(is_active=True, roles__code=Role.EMPLOYEE).order_by("id")[:1]
            )
        return assignment

    def _create_documents(self, spdp, index, created_by, assignment, stage_one):
        if assignment and assignment.status == P16Assignment.Status.ASSIGNED:
            P16Draft.create_for_assignment(assignment, created_by or assignment.kasi_pidum)

        p17 = None
        if index % 5 in (1, 3):
            p17 = P17Draft.create_for_spdp(spdp, created_by)
            SOPForm1BDraft.objects.create(
                p17_draft=p17,
                report_date=spdp.received_date,
                recipient="Kepala Seksi Tindak Pidana Umum",
                sender="Penuntut Umum",
                subject=f"Laporan perkembangan perkara {spdp.letter_number}",
                prosecutor_name=assignment.prosecutors.first().display_name if assignment and assignment.prosecutors.exists() else "",
            )

        if index % 7 == 2:
            SOPForm02Draft.create_for_spdp(spdp, created_by)
        if index % 7 == 5:
            SOPForm03Draft.create_for_spdp(spdp, created_by)

        if index % 4 == 0:
            document_type = CaseDocumentDraft.DocumentType.P18
        elif index % 4 == 1:
            document_type = CaseDocumentDraft.DocumentType.P19
        elif index % 4 == 2:
            document_type = CaseDocumentDraft.DocumentType.P20
        else:
            document_type = CaseDocumentDraft.DocumentType.SOP_FORM_07
        CaseDocumentDraft.create_for_spdp(spdp, document_type, created_by)

        if assignment and index % 3 == 0:
            coordination_type = (
                CoordinationMinutesDraft.CoordinationType.FIRST,
                CoordinationMinutesDraft.CoordinationType.SECOND,
                CoordinationMinutesDraft.CoordinationType.THIRD,
            )[index // 3 % 3]
            CoordinationMinutesDraft.create_for_spdp(spdp, coordination_type, created_by)

        if stage_one and index % 2 == 0:
            P21Draft.create_for_spdp(spdp, created_by)
