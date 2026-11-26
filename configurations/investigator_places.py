def investigator_destination_place(spdp, fallback="Tempat"):
    """Ambil tempat tujuan surat dari unit penyidik yang dipilih pada SPDP."""
    from .models import InvestigatorUnit

    unit_name = str(getattr(spdp, "investigating_unit", "") or "").strip()
    institution_name = str(getattr(spdp, "investigator_agency", "") or "").strip()
    if unit_name:
        units = InvestigatorUnit.objects.filter(name__iexact=unit_name)
        if institution_name:
            matching_institution = units.filter(
                institution__name__iexact=institution_name,
            ).first()
            if matching_institution and matching_institution.place.strip():
                return matching_institution.place.strip()
        unit = units.exclude(place="").first()
        if unit and unit.place.strip():
            return unit.place.strip()
    return str(fallback or "Tempat").strip() or "Tempat"
