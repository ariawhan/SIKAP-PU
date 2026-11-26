from django.template.loader import render_to_string

from .p16_content import sanitize_p16_html


def document_context(draft):
    from configurations.models import InstitutionConfiguration
    from configurations.investigator_places import investigator_destination_place
    from .models import CaseDocumentDraft

    suspects = list(draft.spdp.suspects.all())
    p18 = draft.spdp.case_document_drafts.filter(document_type=CaseDocumentDraft.DocumentType.P18).first()
    p19 = draft.spdp.case_document_drafts.filter(document_type=CaseDocumentDraft.DocumentType.P19).first()
    p21 = getattr(draft.spdp, "p21_draft", None)
    case_file_receipt = draft.spdp.receipts.filter(
        receipt_type="hasil_penyidikan",
    ).order_by("-received_at", "-id").first()
    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    return {
        "draft": draft, "spdp": draft.spdp,
        "institution": institution,
        "investigator_place": investigator_destination_place(
            draft.spdp, institution.city or "Tempat",
        ),
        "suspect_names": ", ".join(item.name for item in suspects) or "---",
        "p18": p18, "p19": p19, "p21": p21,
        "case_file_receipt": case_file_receipt,
    }


def ensure_case_document_sections(draft):
    from configurations.document_templates import render_configured_sections
    from .models import CaseDocumentDraft

    context = document_context(draft)
    prefix = draft.document_type
    defaults = {
        name: sanitize_p16_html(render_to_string(f"cases/case_document_sections/{prefix}_{section}.html", context).strip())
        for name, section in (("subject_html", "subject"), ("legal_basis_html", "legal_basis"), ("body_html", "body"), ("copies_html", "copies"))
    }
    if draft.document_type == CaseDocumentDraft.DocumentType.P19:
        # Petunjuk P-19 ditulis bebas oleh pengguna dalam satu editor Isi.
        defaults["legal_basis_html"] = ""
        defaults["body_html"] = ""
    defaults = render_configured_sections(
        draft.document_type,
        defaults,
        context,
        sanitize_p16_html,
    )
    changed = []
    for name, value in defaults.items():
        if not getattr(draft, name) or draft.last_edited_by_id is None:
            setattr(draft, name, value)
            changed.append(name)
    if changed:
        draft.save(update_fields=(*changed, "updated_at"))
    return changed


def build_case_document_preview(draft):
    return render_to_string("cases/case_document_preview.html", document_context(draft)).strip()
