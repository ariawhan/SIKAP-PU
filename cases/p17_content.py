from html import unescape

from django.template.loader import render_to_string
from django.utils.html import format_html, format_html_join, strip_tags

from .p16_content import sanitize_p16_html


SECTION_TEMPLATES = {
    "subject_html": "cases/p17_sections/subject.html",
    "recipient_html": "cases/p17_sections/recipient.html",
    "body_html": "cases/p17_sections/body.html",
    "copies_html": "cases/p17_sections/copies.html",
}


def request_label(sequence):
    labels = {1: "Pertama", 2: "Kedua", 3: "Ketiga", 4: "Keempat", 5: "Kelima"}
    return labels.get(sequence, f"Ke-{sequence}")


def p17_context(draft):
    from configurations.models import InstitutionConfiguration

    suspects = list(draft.spdp.suspects.all())
    suspect_names = ", ".join(suspect.name for suspect in suspects) or "---"
    return {
        "draft": draft,
        "spdp": draft.spdp,
        "institution": InstitutionConfiguration.objects.first() or InstitutionConfiguration(),
        "suspects": suspects,
        "suspect_names": suspect_names,
        "request_label": request_label(draft.sequence),
    }


def default_p17_recipients(draft):
    from configurations.models import InstitutionConfiguration

    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    unit = (draft.spdp.investigating_unit or draft.spdp.investigator_agency or "Penyidik").strip()
    return [{
        "recipient": unit if unit.lower().startswith("kepala ") else f"Kepala {unit}",
        "place": (institution.city or "Tempat").strip(),
    }]


def normalize_p17_recipients(recipients):
    normalized = []
    common_place = ""
    for item in recipients if isinstance(recipients, list) else []:
        if not isinstance(item, dict):
            continue
        recipient = str(item.get("recipient", "")).strip()
        place = str(item.get("place", "")).strip()
        if recipient:
            if not common_place and place:
                common_place = place[:150]
            normalized.append({"recipient": recipient[:300], "place": ""})
    for item in normalized:
        item["place"] = common_place
    return normalized


def render_p17_recipients(recipients):
    recipients = normalize_p17_recipients(recipients)
    if not recipients:
        return ""
    if len(recipients) == 1:
        item = recipients[0]
        rows = format_html(
            '<div class="p17-recipient-single" data-p17-recipient="{}" data-p17-place="{}"><strong>{}</strong></div>',
            item["recipient"], item["place"], item["recipient"],
        )
    else:
        rows = format_html_join(
            "",
            '<li data-p17-recipient="{}" data-p17-place="{}"><strong>{}</strong></li>',
            ((item["recipient"], item["place"], item["recipient"]) for item in recipients),
        )
        rows = format_html('<ol class="p17-recipient-numbered">{}</ol>', rows)
    # ``format_html`` returns SafeString. Keeping that marker is correct when
    # rendering the document preview, but unsafe as a ModelForm field value:
    # the hidden input would render its quotes unescaped and break the entire
    # editor DOM. Joining converts it back to an ordinary ``str``.
    place = recipients[0]["place"] or "---"
    return "".join([format_html(
        '<div class="p17-recipient-list"><p><strong>Yth.</strong></p>{}'
        '<div class="p17-recipient-place"><span>Di -</span><u>{}</u></div></div>',
        rows, place,
    )])


def p17_recipients_for_editor(draft):
    """Read structured recipients and gracefully initialize legacy drafts."""
    import re

    matches = re.findall(
        r'data-p17-recipient=["\']([^"\']*)["\']\s+data-p17-place=["\']([^"\']*)["\']',
        draft.recipient_html or "",
        flags=re.IGNORECASE,
    )
    if matches:
        return normalize_p17_recipients([
            {"recipient": unescape(recipient), "place": unescape(place)}
            for recipient, place in matches
        ])
    legacy_text = re.sub(r"<br\s*/?>", "\n", draft.recipient_html or "", flags=re.IGNORECASE)
    legacy_text = re.sub(r"</(?:p|div|li)\s*>", "\n", legacy_text, flags=re.IGNORECASE)
    lines = [unescape(line).strip() for line in strip_tags(legacy_text).splitlines() if unescape(line).strip()]
    if lines:
        recipient = re.sub(r"^Yth\.?\s*", "", lines[0], flags=re.IGNORECASE).strip()
        place = ""
        for index, line in enumerate(lines[1:], start=1):
            match = re.match(r"^Di\s*-?\s*(.*)$", line, flags=re.IGNORECASE)
            if match:
                place = match.group(1).strip() or (lines[index + 1] if index + 1 < len(lines) else "")
                break
        if recipient:
            return normalize_p17_recipients([{"recipient": recipient, "place": place}])
    return default_p17_recipients(draft)


def build_default_p17_sections(draft):
    from configurations.document_templates import render_configured_sections

    context = p17_context(draft)
    sections = {
        field_name: sanitize_p16_html(render_to_string(template_name, context).strip())
        for field_name, template_name in SECTION_TEMPLATES.items()
    }
    sections = render_configured_sections("p17", sections, context, sanitize_p16_html)
    sections["subject_html"] = unescape(strip_tags(sections["subject_html"])).strip()
    sections["recipient_html"] = render_p17_recipients(default_p17_recipients(draft))
    return sections


def ensure_p17_sections(draft):
    defaults = build_default_p17_sections(draft)
    changed_fields = []
    for field_name, default_value in defaults.items():
        # Draf yang belum pernah disimpan pengguna masih memakai konten bawaan,
        # sehingga aman diselaraskan ketika format resmi diperbarui.
        if not getattr(draft, field_name) or draft.last_edited_by_id is None:
            setattr(draft, field_name, default_value)
            changed_fields.append(field_name)
    if changed_fields:
        draft.save(update_fields=(*changed_fields, "updated_at"))
    return changed_fields


def build_p17_preview(draft):
    return render_to_string("cases/p17_preview_document.html", p17_context(draft)).strip()
