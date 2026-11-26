from django.core.management.base import BaseCommand
from django.db import transaction

from configurations.models import InvestigatorInstitution, InvestigatorUnit


INVESTIGATOR_DATA = (
    (
        "Kepolisian Republik Indonesia",
        (
            "Polres Buleleng",
            "Polsek Banjar",
            "Polsek Buleleng",
            "Polsek Busungbiu",
            "Polsek Gerokgak",
            "Polsek Kubutambahan",
            "Polsek Sawan",
            "Polsek Seririt",
            "Polsek Sukasada",
            "Polsek Tejakula",
        ),
    ),
    (
        "Badan Narkotika Nasional Republik Indonesia",
        (
            "BNN Provinsi Bali",
            "BNN Kabupaten Buleleng",
        ),
    ),
    (
        "Direktorat Jenderal Imigrasi",
        ("Kantor Imigrasi Kelas II TPI Singaraja",),
    ),
    (
        "Direktorat Jenderal Bea dan Cukai",
        (
            "Kantor Pengawasan dan Pelayanan Bea dan Cukai Tipe Madya Pabean A Denpasar",
        ),
    ),
    (
        "PPNS Pemerintah Kabupaten Buleleng",
        (
            "Satuan Polisi Pamong Praja Kabupaten Buleleng",
            "Dinas Perhubungan Kabupaten Buleleng",
            "Dinas Lingkungan Hidup Kabupaten Buleleng",
        ),
    ),
)

UNIT_PLACES = {
    "Satreskrim Polres Buleleng": "Buleleng",
    "Polres Buleleng": "Buleleng",
    "Polsek Banjar": "Banjar",
    "Polsek Buleleng": "Buleleng",
    "Polsek Busungbiu": "Busungbiu",
    "Polsek Gerokgak": "Gerokgak",
    "Polsek Kubutambahan": "Kubutambahan",
    "Polsek Sawan": "Sawan",
    "Polsek Seririt": "Seririt",
    "Polsek Sukasada": "Sukasada",
    "Polsek Tejakula": "Tejakula",
    "BNN Provinsi Bali": "Denpasar",
    "BNN Kabupaten Buleleng": "Buleleng",
    "Kantor Imigrasi Kelas II TPI Singaraja": "Singaraja",
    "Kantor Pengawasan dan Pelayanan Bea dan Cukai Tipe Madya Pabean A Denpasar": "Denpasar",
    "Satuan Polisi Pamong Praja Kabupaten Buleleng": "Buleleng",
    "Dinas Perhubungan Kabupaten Buleleng": "Buleleng",
    "Dinas Lingkungan Hidup Kabupaten Buleleng": "Buleleng",
}


class Command(BaseCommand):
    help = "Mengisi data awal instansi dan unit pelaksana penyidik tanpa duplikasi."

    @transaction.atomic
    def handle(self, *args, **options):
        institution_created = 0
        unit_created = 0

        police = InvestigatorInstitution.objects.filter(
            name="Kepolisian Republik Indonesia"
        ).first()
        if police:
            typo = police.units.filter(name="Pores Buleleng").first()
            correct_exists = police.units.filter(name="Polres Buleleng").exists()
            if typo and not correct_exists:
                typo.name = "Polres Buleleng"
                typo.save(update_fields=["name", "updated_at"])
                self.stdout.write("[DIPERBAIKI] Pores Buleleng -> Polres Buleleng")

        for institution_name, units in INVESTIGATOR_DATA:
            institution, created = InvestigatorInstitution.objects.get_or_create(
                name=institution_name,
                defaults={"is_active": True},
            )
            institution_created += int(created)

            for unit_name in units:
                unit, created = InvestigatorUnit.objects.get_or_create(
                    institution=institution,
                    name=unit_name,
                    defaults={
                        "is_active": True,
                        "place": UNIT_PLACES.get(unit_name, ""),
                    },
                )
                if not created and not unit.place and UNIT_PLACES.get(unit_name):
                    unit.place = UNIT_PLACES[unit_name]
                    unit.save(update_fields=("place", "updated_at"))
                unit_created += int(created)

        for name_fragment, place in (
            ("Buleleng", "Buleleng"),
            ("Singaraja", "Singaraja"),
            ("Denpasar", "Denpasar"),
        ):
            InvestigatorUnit.objects.filter(
                name__icontains=name_fragment, place="",
            ).update(place=place)

        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai: {institution_created} instansi baru dan "
                f"{unit_created} unit pelaksana baru ditambahkan."
            )
        )
