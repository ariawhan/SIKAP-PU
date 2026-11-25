from dataclasses import dataclass
from datetime import date, timedelta

from django.urls import reverse
from django.utils import timezone

from .models import P21Draft, SPDP


PREPROSECUTION_PERIOD_DAYS = 30
SPDP_PERIOD_DAYS = 2
STAGE_ONE_PERIOD_DAYS = 7
FOLLOW_UP_PERIOD_DAYS = 14


@dataclass(frozen=True)
class CaseDeadline:
    spdp: SPDP
    stage_key: str
    stage_label: str
    document_id: int
    letter_number: str
    start_date: date
    due_date: date
    period_days: int
    elapsed_days: int
    remaining_days: int
    color_class: str
    badge_title: str
    badge_value: str
    status_text: str
    action_text: str

    @property
    def automatic_due(self):
        return self.elapsed_days in self.automatic_reminder_days

    @property
    def automatic_reminder_days(self):
        return (self.period_days - 2, self.period_days - 1, self.period_days)

    @property
    def target_url(self):
        route_name = {
            "spdp": "cases:spdp_detail",
            "p16": "cases:p16_draft_detail",
            "p17": "cases:p17_draft_detail",
            "sop02": "cases:sop_form_02_detail",
            "stage1": "cases:stage_one_detail",
            "p19": "cases:p19_detail",
            "p21": "cases:p21_draft_detail",
        }[self.stage_key]
        target_pk = self.spdp.pk if self.stage_key == "spdp" else self.document_id
        return reverse(route_name, args=[target_pk])

    @property
    def remaining_title(self):
        if self.remaining_days > 2:
            return "Sisa"
        if self.remaining_days > 0:
            return "Segera"
        if self.remaining_days == 0:
            return "Tenggat"
        return "Lewat"

    @property
    def remaining_value(self):
        if self.remaining_days > 0:
            return f"{self.remaining_days} hari"
        if self.remaining_days == 0:
            return "Hari ini"
        return f"{abs(self.remaining_days)} hari"

    @property
    def remaining_display(self):
        if self.remaining_days > 0:
            return f"Sisa {self.remaining_days} hari"
        if self.remaining_days == 0:
            return "Hari ini"
        return f"Terlambat {abs(self.remaining_days)} hari"


def _is_official(number):
    return bool(number and not str(number).upper().startswith("DRAFT/"))


def case_deadline_for_spdp(spdp, today):
    stage = None
    documents = {
        item.document_type: item
        for item in spdp.case_document_drafts.all()
        if _is_official(item.letter_number)
    }
    p21 = getattr(spdp, "p21_draft", None)
    stage_one = getattr(spdp, "stage_one", None)

    if p21 and p21.status == P21Draft.Status.COMPLETED:
        return None
    if "sop07" in documents:
        return None
    if p21 and _is_official(p21.letter_number):
        stage = (
            "p21", "P-21", p21.pk, p21.letter_number, p21.letter_date,
            FOLLOW_UP_PERIOD_DAYS,
            "Segera tindak lanjuti penyerahan tersangka dan barang bukti (Tahap 2).",
        )
    elif "p20" in documents:
        return None
    elif "p19" in documents:
        p19 = documents["p19"]
        stage = (
            "p19", "P-19", p19.pk, p19.letter_number, p19.letter_date,
            FOLLOW_UP_PERIOD_DAYS,
            "Segera tindak lanjuti pengembalian berkas perkara dari penyidik.",
        )
    elif "p18" in documents:
        return None
    elif stage_one:
        stage = (
            "stage1", "Tahap 1", stage_one.pk, stage_one.case_file_number,
            timezone.localtime(stage_one.completed_at).date(), STAGE_ONE_PERIOD_DAYS,
            "Segera selesaikan penelitian berkas dan terbitkan P-18/P-19 atau P-21.",
        )
    else:
        sop03 = getattr(spdp, "sop_form_03_draft", None)
        if sop03 and _is_official(sop03.letter_number):
            return None
        sop02 = getattr(spdp, "sop_form_02_draft", None)
        if sop02 and _is_official(sop02.letter_number):
            stage = (
                "sop02", "SOP Form 2", sop02.pk, sop02.letter_number,
                sop02.letter_date, PREPROSECUTION_PERIOD_DAYS,
                "Segera tindak lanjuti perkara atau input Tahap 1 apabila berkas telah diterima.",
            )
        else:
            p17_drafts = list(spdp.p17_drafts.all())
            p17 = next((item for item in p17_drafts if _is_official(item.letter_number)), None)
            if p17:
                stage = (
                    "p17", "P-17", p17.pk, p17.letter_number, p17.letter_date,
                    PREPROSECUTION_PERIOD_DAYS,
                    "Segera tindak lanjuti perkara atau input Tahap 1 apabila berkas telah diterima.",
                )
            else:
                assignment = getattr(spdp, "p16_assignment", None)
                p16 = getattr(assignment, "draft", None) if assignment else None
                if p16 and _is_official(p16.draft_number):
                    stage = (
                        "p16", "P-16", p16.pk, p16.draft_number, p16.letter_date,
                        PREPROSECUTION_PERIOD_DAYS,
                        "Segera tindak lanjuti perkara atau input Tahap 1 apabila berkas telah diterima.",
                    )
                else:
                    stage = (
                        "spdp", "Penerbitan P-16", spdp.pk, spdp.letter_number,
                        spdp.received_date, SPDP_PERIOD_DAYS,
                        "Segera proses perkara dan terbitkan surat P-16.",
                    )
    if not stage:
        return None

    (
        stage_key, stage_label, document_id, letter_number, start_date,
        period_days, action_text,
    ) = stage
    elapsed_days = max((today - start_date).days, 0)
    due_date = start_date + timedelta(days=period_days)
    remaining_days = (due_date - today).days
    warning_day = period_days - 2
    if elapsed_days < warning_day:
        color_class = "safe"
        badge_title = "Aktif"
        badge_value = f"Hari ke-{elapsed_days}"
        status_text = f"tersisa {remaining_days} hari"
    elif elapsed_days < period_days:
        color_class = "warning"
        badge_title = "Waspada"
        badge_value = f"Hari ke-{elapsed_days}"
        status_text = f"memasuki hari ke-{elapsed_days}"
    else:
        color_class = "overdue"
        badge_title = "Tenggat" if elapsed_days == period_days else "Terlambat"
        badge_value = f"Hari ke-{period_days}" if elapsed_days == period_days else f"+{elapsed_days - period_days} hari"
        status_text = "batas waktu hari ini" if elapsed_days == period_days else f"terlambat {elapsed_days - period_days} hari"
    return CaseDeadline(
        spdp=spdp,
        stage_key=stage_key,
        stage_label=stage_label,
        document_id=document_id,
        letter_number=letter_number,
        start_date=start_date,
        due_date=due_date,
        period_days=period_days,
        elapsed_days=elapsed_days,
        remaining_days=remaining_days,
        color_class=color_class,
        badge_title=badge_title,
        badge_value=badge_value,
        status_text=status_text,
        action_text=action_text,
    )


def active_case_deadlines(today):
    queryset = (
        SPDP.objects.select_related(
            "stage_one", "sop_form_02_draft", "sop_form_03_draft",
            "p16_assignment__draft", "p16_assignment__kasi_pidum", "p21_draft",
        )
        .prefetch_related(
            "suspects", "p17_drafts", "case_document_drafts",
            "p16_assignment__prosecutors", "p16_assignment__administrative_staff",
        )
    )
    deadlines = [case_deadline_for_spdp(spdp, today) for spdp in queryset]
    deadlines = [item for item in deadlines if item]
    deadlines.sort(key=lambda item: (item.due_date, item.spdp.pk))
    return deadlines
