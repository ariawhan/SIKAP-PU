from datetime import timedelta

from django.template.loader import render_to_string

from .p16_content import sanitize_p16_html


SECTION_TEMPLATES = {
    "subject_html": "cases/p21_sections/subject.html",
    "legal_basis_html": "cases/p21_sections/legal_basis.html",
    "body_html": "cases/p21_sections/body.html",
    "copies_html": "cases/p21_sections/copies.html",
}


def p21_context(draft):
    from configurations.models import InstitutionConfiguration

    suspects = list(draft.spdp.suspects.all())
    case_file_receipt = draft.spdp.receipts.filter(
        receipt_type="hasil_penyidikan",
    ).order_by("-received_at", "-id").first()
    return {
        "draft": draft,
        "spdp": draft.spdp,
        "institution": InstitutionConfiguration.objects.first() or InstitutionConfiguration(),
        "suspect_names": ", ".join(suspect.name for suspect in suspects) or "---",
        "handover_deadline": draft.letter_date + timedelta(days=14),
        "case_file_receipt": case_file_receipt,
    }


def build_default_p21_sections(draft):
    from configurations.document_templates import render_configured_sections

    context = p21_context(draft)
    defaults = {
        field_name: sanitize_p16_html(render_to_string(template_name, context).strip())
        for field_name, template_name in SECTION_TEMPLATES.items()
    }
    return render_configured_sections("p21", defaults, context, sanitize_p16_html)


def ensure_p21_sections(draft):
    defaults = build_default_p21_sections(draft)
    changed_fields = []
    for field_name, default_value in defaults.items():
        if not getattr(draft, field_name) or draft.last_edited_by_id is None:
            setattr(draft, field_name, default_value)
            changed_fields.append(field_name)
    if changed_fields:
        draft.save(update_fields=(*changed_fields, "updated_at"))
    return changed_fields


def build_p21_preview(draft):
    return render_to_string("cases/p21_preview_document.html", p21_context(draft)).strip()
