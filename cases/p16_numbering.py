import re

from configurations.models import InstitutionConfiguration, LetterNumberCode


class P16NumberingError(ValueError):
    pass


def normalize_p16_letter_code(code):
    normalized = (code or "").strip()
    if normalized and not re.search(r"\.\d+$", normalized):
        normalized = f"{normalized}.1"
    return normalized


def p16_number_parts(assignment):
    institution = InstitutionConfiguration.objects.first()
    region_code = (institution.institution_code if institution else "").strip()
    directorate = (assignment.spdp.directorate if assignment and assignment.spdp else "").strip()
    configured_code = LetterNumberCode.objects.filter(directorate__iexact=directorate).first()
    return region_code, normalize_p16_letter_code(configured_code.code if configured_code else "")


def build_p16_number(sequence, letter_date, assignment):
    sequence = (sequence or "").strip().upper()
    if not re.fullmatch(r"\d+[A-Z]?", sequence):
        raise P16NumberingError("Nomor urut harus berupa angka dan boleh memiliki satu huruf di belakang.")
    numeric_sequence = re.match(r"\d+", sequence).group(0)
    if int(numeric_sequence) < 1:
        raise P16NumberingError("Nomor urut harus lebih besar dari 0.")
    if not letter_date:
        raise P16NumberingError("Tanggal surat wajib diisi.")
    region_code, letter_code = p16_number_parts(assignment)
    if not region_code:
        raise P16NumberingError("Kode wilayah belum diisi pada Konfigurasi Instansi.")
    if not letter_code:
        raise P16NumberingError("Kode surat untuk direktorat perkara belum dikonfigurasi.")
    return f"PRINT-{sequence}/{region_code}/{letter_code}/{letter_date.month:02d}/{letter_date.year}"


def extract_p16_sequence(number):
    match = re.match(r"^PRINT-(\d+[A-Z]?)/", (number or "").strip(), re.IGNORECASE)
    return match.group(1) if match else ""
