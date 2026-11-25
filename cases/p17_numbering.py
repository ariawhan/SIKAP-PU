import re

from configurations.models import InstitutionConfiguration, LetterNumberCode
from .p16_numbering import normalize_p16_letter_code


class P17NumberingError(ValueError):
    pass


def p17_number_parts(spdp):
    institution = InstitutionConfiguration.objects.first()
    region_code = (institution.institution_code if institution else "").strip()
    directorate = (getattr(spdp, "directorate", "") or "").strip()
    configured_code = LetterNumberCode.objects.filter(directorate__iexact=directorate).first()
    return region_code, normalize_p16_letter_code(configured_code.code if configured_code else "")


def build_p17_number(sequence, letter_date, spdp):
    sequence = (sequence or "").strip()
    if not re.fullmatch(r"\d+", sequence) or int(sequence) < 1:
        raise P17NumberingError("Nomor urut hanya boleh berisi angka lebih besar dari 0.")
    if not letter_date:
        raise P17NumberingError("Tanggal surat wajib diisi.")
    region_code, letter_code = p17_number_parts(spdp)
    if not region_code:
        raise P17NumberingError("Kode wilayah belum diisi pada Konfigurasi Instansi.")
    if not letter_code:
        raise P17NumberingError("Kode surat untuk direktorat perkara belum dikonfigurasi.")
    return f"B-{sequence}/{region_code}/{letter_code}/{letter_date.month:02d}/{letter_date.year}"


def extract_p17_sequence(number):
    match = re.match(r"^B-(\d+)/", (number or "").strip(), re.IGNORECASE)
    return match.group(1) if match else ""
