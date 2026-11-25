from django.template.loader import render_to_string

from .p16_content import sanitize_p16_html


BODY_TEMPLATES = {
    "ba1": "cases/coordination_sections/ba1_body.html",
    "ba2": "cases/coordination_sections/ba2_body.html",
    "ba3": "cases/coordination_sections/ba3_body.html",
}


def coordination_context(draft):
    from configurations.models import InstitutionConfiguration

    assignment = getattr(draft.spdp, "p16_assignment", None)
    p16 = getattr(assignment, "draft", None) if assignment else None
    suspects = list(draft.spdp.suspects.all())
    return {
        "draft": draft,
        "spdp": draft.spdp,
        "institution": InstitutionConfiguration.objects.first() or InstitutionConfiguration(),
        "p16": p16,
        "suspect_names": ", ".join(item.name for item in suspects) or "---",
    }


def build_default_coordination_body(draft):
    return sanitize_p16_html(
        render_to_string(BODY_TEMPLATES[draft.coordination_type], coordination_context(draft)).strip()
    )


def ensure_coordination_body(draft):
    if not draft.body_html or draft.last_edited_by_id is None:
        draft.body_html = build_default_coordination_body(draft)
        draft.save(update_fields=("body_html", "updated_at"))
        return True
    return False


def build_coordination_preview(draft):
    return render_to_string("cases/coordination_preview_document.html", coordination_context(draft)).strip()
