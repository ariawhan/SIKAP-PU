from django.template.loader import render_to_string

from .p16_content import sanitize_p16_html


def sop_context(draft):
    from configurations.models import InstitutionConfiguration
    from configurations.investigator_places import investigator_destination_place

    suspects = list(draft.spdp.suspects.all())
    latest_p17 = draft.spdp.p17_drafts.order_by("-sequence").first()
    sop_form_02 = getattr(draft.spdp, "sop_form_02_draft", None)
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    return {
        "draft": draft,
        "spdp": draft.spdp,
        "institution": institution,
        "investigator_place": investigator_destination_place(
            draft.spdp, institution.city or "Tempat",
        ),
        "suspect_names": ", ".join(suspect.name for suspect in suspects) or "---",
        "latest_p17": latest_p17,
        "sop_form_02": sop_form_02,
    }


def _ensure_sections(draft, prefix):
    from configurations.document_templates import render_configured_sections

    context = sop_context(draft)
    defaults = {
        field: sanitize_p16_html(render_to_string(f"cases/{prefix}_sections/{name}.html", context).strip())
        for field, name in (("subject_html", "subject"), ("body_html", "body"), ("copies_html", "copies"))
    }
    template_key = "sop02" if prefix == "sop_form_02" else "sop03"
    defaults = render_configured_sections(template_key, defaults, context, sanitize_p16_html)
    changed = []
    for field, value in defaults.items():
        if not getattr(draft, field) or draft.last_edited_by_id is None:
            setattr(draft, field, value)
            changed.append(field)
    if changed:
        draft.save(update_fields=(*changed, "updated_at"))
    return changed


def ensure_sop_form_02_sections(draft):
    return _ensure_sections(draft, "sop_form_02")


def ensure_sop_form_03_sections(draft):
    return _ensure_sections(draft, "sop_form_03")


def build_sop_preview(draft, form_code, show_motto):
    context = sop_context(draft)
    context.update({"form_code": form_code, "show_motto": show_motto})
    return render_to_string("cases/sop_form_preview_document.html", context).strip()
