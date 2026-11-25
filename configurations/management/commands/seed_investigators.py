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
                _, created = InvestigatorUnit.objects.get_or_create(
                    institution=institution,
                    name=unit_name,
                    defaults={"is_active": True},
                )
                unit_created += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Selesai: {institution_created} instansi baru dan "
                f"{unit_created} unit pelaksana baru ditambahkan."
            )
        )
