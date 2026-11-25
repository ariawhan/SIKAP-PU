from django.template.loader import render_to_string

from .models import SOPForm1BDraft
from .p16_content import sanitize_p16_html
from .p17_content import p17_context, request_label


SECTION_TEMPLATES = {
    "legal_basis_html": "cases/sop_form_1b_sections/legal_basis.html",
    "facts_html": "cases/sop_form_1b_sections/facts.html",
    "legal_analysis_html": "cases/sop_form_1b_sections/legal_analysis.html",
    "conclusion_html": "cases/sop_form_1b_sections/conclusion.html",
}


def _number_in_indonesian(value):
    words = (
        "nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh",
        "delapan", "sembilan", "sepuluh", "sebelas",
    )
    value = int(value)
    if value < 12:
        return words[value]
    if value < 20:
        return f"{_number_in_indonesian(value - 10)} belas"
    if value < 100:
        tens, remainder = divmod(value, 10)
        suffix = f" {_number_in_indonesian(remainder)}" if remainder else ""
        return f"{_number_in_indonesian(tens)} puluh{suffix}"
    if value < 200:
        suffix = f" {_number_in_indonesian(value - 100)}" if value > 100 else ""
        return f"seratus{suffix}"
    if value < 1000:
        hundreds, remainder = divmod(value, 100)
        suffix = f" {_number_in_indonesian(remainder)}" if remainder else ""
        return f"{_number_in_indonesian(hundreds)} ratus{suffix}"
    return str(value)


def _suspect_label(p17_draft):
    labels = []
    for suspect in p17_draft.spdp.suspects.all():
        label = suspect.name.strip()
        if suspect.alias and suspect.alias.lower() not in label.lower():
            label = f"{label} Alias {suspect.alias.strip()}"
        labels.append(label.upper())
    return ", ".join(labels) or "---"


def sop_form_1b_context(p17_draft, sop_draft=None):
    context = p17_context(p17_draft)
    assignment = getattr(p17_draft.spdp, "p16_assignment", None)
    p16_draft = getattr(assignment, "draft", None) if assignment else None
    prosecutor = assignment.prosecutors.order_by("id").first() if assignment else None
    elapsed_days = max((p17_draft.letter_date - p17_draft.spdp.received_date).days, 0)
    context.update({
        "p17_draft": p17_draft,
        "sop_draft": sop_draft,
        "assignment": assignment,
        "p16_draft": p16_draft,
        "prosecutor": prosecutor,
        "suspect_label": _suspect_label(p17_draft),
        "elapsed_days": elapsed_days,
        "elapsed_days_words": _number_in_indonesian(elapsed_days),
        "request_label": request_label(p17_draft.sequence),
    })
    return context


def build_default_sop_form_1b(p17_draft):
    from configurations.document_templates import render_configured_sections

    context = sop_form_1b_context(p17_draft)
    institution = context["institution"]
    prosecutor = context["prosecutor"]
    suspect_label = context["suspect_label"]
    defaults = {
        "report_date": p17_draft.letter_date,
        "recipient": institution.leader_title or "Kepala Kejaksaan Negeri",
        "sender": f"Jaksa / Penuntut Umum (P-16) Perkara A.n. Tersangka {suspect_label}",
        "attachment": "1 (satu) berkas",
        "subject": f"Laporan Penuntut Umum Perkembangan Hasil Penyidikan Perkara A.n. Tersangka {suspect_label}",
        "closing": "Demikian untuk menjadi periksa dan mohon petunjuk.",
        "prosecutor_name": prosecutor.display_name if prosecutor else "",
        "prosecutor_rank": prosecutor.rank if prosecutor else "",
        "prosecutor_nip": prosecutor.nip if prosecutor else "",
        "kasi_opinion_html": "<p><br></p>",
        "leader_instruction_html": "<p><br></p>",
    }
    for field_name, template_name in SECTION_TEMPLATES.items():
        defaults[field_name] = sanitize_p16_html(
            render_to_string(template_name, context).strip()
        )
    configured = render_configured_sections(
        "sop1b",
        {field_name: defaults[field_name] for field_name in SECTION_TEMPLATES},
        context,
        sanitize_p16_html,
    )
    defaults.update(configured)
    return defaults


def ensure_sop_form_1b(p17_draft):
    defaults = build_default_sop_form_1b(p17_draft)
    sop_draft, created = SOPForm1BDraft.objects.get_or_create(
        p17_draft=p17_draft,
        defaults=defaults,
    )
    if not created and sop_draft.last_edited_by_id is None:
        for field_name, value in defaults.items():
            setattr(sop_draft, field_name, value)
        sop_draft.save(update_fields=(*defaults.keys(), "updated_at"))
    return sop_draft


def build_sop_form_1b_preview(sop_draft):
    context = sop_form_1b_context(sop_draft.p17_draft, sop_draft)
    return render_to_string("cases/sop_form_1b_preview_document.html", context).strip()
