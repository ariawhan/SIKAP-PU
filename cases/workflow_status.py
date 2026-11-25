from .models import CaseDocumentDraft, P16Assignment, P21Draft, SPDP


def letter_number_is_issued(number):
    return bool(number and not str(number).upper().startswith("DRAFT/"))


def spdp_workflow_status(spdp):
    documents = {
        draft.document_type: draft
        for draft in spdp.case_document_drafts.all()
    }

    sop07 = documents.get(CaseDocumentDraft.DocumentType.SOP_FORM_07)
    p20 = documents.get(CaseDocumentDraft.DocumentType.P20)
    sop03 = getattr(spdp, "sop_form_03_draft", None)
    terminal_documents = (
        ("SOP Form 7", sop07, bool(sop07 and letter_number_is_issued(sop07.letter_number))),
        (
            "P-20",
            p20,
            bool(p20 and p20.sipede_status == CaseDocumentDraft.SipedeStatus.UPLOADED),
        ),
        ("SOP Form 3", sop03, bool(sop03 and letter_number_is_issued(sop03.letter_number))),
    )
    for label, draft, is_issued in terminal_documents:
        if draft and is_issued:
            return {
                "stage": label,
                "label": "Diberhentikan",
                "detail": f"{label} telah terbit",
                "badge_class": "red",
            }

    p21 = getattr(spdp, "p21_draft", None)
    if p21 and p21.status == P21Draft.Status.COMPLETED:
        return {
            "stage": "P-21",
            "label": "Sudah P-21",
            "detail": "P-21 sudah dilaksanakan",
            "badge_class": "green",
        }

    if spdp.status == SPDP.Status.RETURNED:
        return {
            "stage": "SPDP",
            "label": "Dikembalikan",
            "detail": "SPDP dikembalikan untuk perbaikan",
            "badge_class": "amber",
        }

    def document_status(label, number):
        return {
            "stage": label,
            "label": f"Proses {label}",
            "detail": f"{label} terbit" if letter_number_is_issued(number) else f"Draf {label}",
            "badge_class": "amber",
        }

    stages = (
        ("SOP Form 7", documents.get(CaseDocumentDraft.DocumentType.SOP_FORM_07)),
        ("P-20", documents.get(CaseDocumentDraft.DocumentType.P20)),
        ("P-21", getattr(spdp, "p21_draft", None)),
        ("P-19", documents.get(CaseDocumentDraft.DocumentType.P19)),
        ("P-18", documents.get(CaseDocumentDraft.DocumentType.P18)),
    )
    for label, draft in stages:
        if draft:
            return document_status(label, draft.letter_number)

    if getattr(spdp, "stage_one", None):
        return {
            "stage": "Tahap 1",
            "label": "Proses Tahap 1",
            "detail": "Berkas perkara telah diterima",
            "badge_class": "amber",
        }

    sop03 = getattr(spdp, "sop_form_03_draft", None)
    if sop03:
        return document_status("SOP Form 3", sop03.letter_number)

    sop02 = getattr(spdp, "sop_form_02_draft", None)
    if sop02:
        return document_status("SOP Form 2", sop02.letter_number)

    p17_drafts = list(spdp.p17_drafts.all())
    if p17_drafts:
        p17 = max(p17_drafts, key=lambda draft: (draft.sequence, draft.created_at))
        return document_status("P-17", p17.letter_number)

    assignment = getattr(spdp, "p16_assignment", None)
    if assignment:
        p16 = getattr(assignment, "draft", None)
        if p16:
            return document_status("P-16", p16.draft_number)
        detail = (
            "Menunggu penunjukan Jaksa"
            if assignment.status == P16Assignment.Status.WAITING_PROSECUTOR
            else "Jaksa ditunjuk, menunggu draf P-16"
        )
        return {
            "stage": "P-16",
            "label": "Proses P-16",
            "detail": detail,
            "badge_class": "amber",
        }

    if spdp.status == SPDP.Status.PROCESS:
        return {
            "stage": "P-16",
            "label": "Proses P-16",
            "detail": "Menunggu penunjukan Kasi Pidum",
            "badge_class": "amber",
        }
    return {
        "stage": "SPDP",
        "label": "Menunggu P-16",
        "detail": "SPDP telah diterima",
        "badge_class": "blue",
    }
