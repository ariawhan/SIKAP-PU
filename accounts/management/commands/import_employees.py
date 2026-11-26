import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Role, User


class Command(BaseCommand):
    help = "Impor atau perbarui data pegawai dari file Excel daftar pegawai."

    def add_arguments(self, parser):
        parser.add_argument("xlsx_path", type=Path)

    def handle(self, *args, **options):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise CommandError("openpyxl belum terpasang. Jalankan pip install -r requirements.txt.") from exc

        path = options["xlsx_path"]
        if not path.is_file():
            raise CommandError(f"File tidak ditemukan: {path}")
        sheet = load_workbook(path, data_only=True, read_only=True).active
        headers = [str(cell.value or "").strip() for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
        required = {"Nama", "Jabatan", "Gol/Pangkat", "NIP / NRP", "Status Pegawai"}
        if not required.issubset(headers):
            raise CommandError("Format Excel tidak sesuai daftar pegawai.")
        index = {name: headers.index(name) for name in required}
        roles = {role.code: role for role in Role.objects.all()}
        missing = {Role.KASI_PIDUM, Role.PROSECUTOR, Role.EMPLOYEE} - roles.keys()
        if missing:
            raise CommandError(f"Role belum tersedia: {', '.join(sorted(missing))}")

        created = updated = skipped = 0
        with transaction.atomic():
            for values in sheet.iter_rows(min_row=2, values_only=True):
                if str(values[index["Status Pegawai"]] or "").strip().lower() != "aktif":
                    skipped += 1
                    continue
                name = str(values[index["Nama"]] or "").strip()
                nip, nrp = self._identity(values[index["NIP / NRP"]])
                if not name or not nip:
                    skipped += 1
                    continue
                rank, grade = self._rank_and_grade(values[index["Gol/Pangkat"]])
                position = str(values[index["Jabatan"]] or "").strip()
                defaults = {
                    "username": nip,
                    "email": f"{nip}@pegawai.local",
                    "first_name": name,
                    "nip": nip,
                    "nrp": nrp,
                    "rank": rank,
                    "grade": grade,
                    "position": position,
                    "is_active": True,
                }
                user = User.objects.filter(nip=nip).first()
                if user is None:
                    user = User.objects.filter(username=nip).first()
                if user is None:
                    user = User(**defaults)
                    user.set_unusable_password()
                    user.save()
                    created += 1
                else:
                    for field, value in defaults.items():
                        setattr(user, field, value)
                    user.save()
                    updated += 1
                assigned = [roles[Role.EMPLOYEE]]
                normalized_position = position.lower()
                if "kepala seksi tindak pidana umum" in normalized_position:
                    assigned.append(roles[Role.KASI_PIDUM])
                if "jaksa" in rank.lower():
                    assigned.append(roles[Role.PROSECUTOR])
                user.roles.set(assigned)
        self.stdout.write(self.style.SUCCESS(f"Impor selesai: {created} dibuat, {updated} diperbarui, {skipped} dilewati."))

    @staticmethod
    def _identity(value):
        parts = re.findall(r"\d+", str(value or ""))
        return (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")

    @staticmethod
    def _rank_and_grade(value):
        raw = " ".join(str(value or "").split())
        grade_match = re.search(r"\b(?:I|II|III|IV)/[a-e]\b", raw, re.IGNORECASE)
        grade = grade_match.group(0).upper() if grade_match else ""
        parenthetical = re.findall(r"\(([^)]*)\)", raw)
        rank = next((item.strip() for item in parenthetical if "jaksa" in item.lower() or "wira" in item.lower()), "")
        if not rank:
            rank = re.sub(r"\([^)]*\)", "", raw)
            rank = re.sub(r"\b(?:I|II|III|IV)/[a-e]\b", "", rank, flags=re.IGNORECASE).strip(" /-")
        return rank, grade
