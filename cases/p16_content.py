from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.template.loader import render_to_string


ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "div", "em", "h1", "h2", "h3", "h4",
    "hr", "i", "img", "li", "ol", "p", "section", "span", "strong",
    "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
VOID_TAGS = {"br", "hr", "img"}
BLOCKED_TAGS = {"script", "style", "iframe", "object", "embed", "form", "input", "button"}
GLOBAL_ATTRIBUTES = {
    "class", "style", "title", "data-p16-page", "data-p16-group",
    "data-p16-output", "data-p16-section", "data-p16-instruction-page-two",
}
TAG_ATTRIBUTES = {
    "a": {"href", "target"}, "img": {"src", "alt", "width", "height"},
    "ol": {"start", "type"}, "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
ALLOWED_STYLES = {
    "background-color", "border", "border-bottom", "border-collapse", "border-left",
    "border-right", "border-top", "color", "font-size", "font-style", "font-weight",
    "height", "letter-spacing", "line-height", "margin", "margin-bottom", "margin-left",
    "margin-right", "margin-top", "padding", "padding-bottom", "padding-left",
    "padding-right", "padding-top", "text-align", "text-decoration", "text-indent",
    "text-transform", "vertical-align", "white-space", "width",
}


def _safe_style(value):
    declarations = []
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        name, raw_value = declaration.split(":", 1)
        name, raw_value = name.strip().lower(), raw_value.strip()
        lowered = raw_value.lower()
        if name in ALLOWED_STYLES and not any(token in lowered for token in ("url(", "expression", "javascript:", "@import")):
            declarations.append(f"{name}: {raw_value}")
    return "; ".join(declarations)


def _safe_url(value, image=False):
    stripped = value.strip()
    lowered = stripped.lower()
    if image and lowered.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,", "data:image/gif;base64,")):
        return stripped
    parsed = urlparse(stripped)
    if parsed.scheme in ("http", "https", "mailto") or (not parsed.scheme and not stripped.startswith("//")):
        return stripped
    return ""


class P16HTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.blocked_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in BLOCKED_TAGS:
            self.blocked_depth += 1
            return
        if self.blocked_depth or tag not in ALLOWED_TAGS:
            return
        allowed = GLOBAL_ATTRIBUTES | TAG_ATTRIBUTES.get(tag, set())
        safe_attrs = []
        for name, value in attrs:
            name, value = name.lower(), value or ""
            if name not in allowed:
                continue
            if name == "style":
                value = _safe_style(value)
            elif name == "href":
                value = _safe_url(value)
            elif name == "src":
                value = _safe_url(value, image=True)
            elif name == "target" and value not in ("_blank", "_self"):
                value = "_self"
            if value:
                safe_attrs.append(f' {name}="{escape(value, quote=True)}"')
        self.output.append(f"<{tag}{''.join(safe_attrs)}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in BLOCKED_TAGS:
            self.blocked_depth = max(0, self.blocked_depth - 1)
            return
        if not self.blocked_depth and tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.output.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.blocked_depth:
            self.output.append(escape(data))

    def handle_entityref(self, name):
        if not self.blocked_depth:
            self.output.append(f"&{name};")

    def handle_charref(self, name):
        if not self.blocked_depth:
            self.output.append(f"&#{name};")


def sanitize_p16_html(value):
    sanitizer = P16HTMLSanitizer()
    sanitizer.feed(value or "")
    sanitizer.close()
    return "".join(sanitizer.output)


SECTION_TEMPLATES = {
    "subject": "cases/p16_sections/subject.html",
    "consideration_html": "cases/p16_sections/consideration.html",
    "legal_basis_html": "cases/p16_sections/legal_basis.html",
    "offense_summary_html": "cases/p16_sections/offense_summary.html",
    "recipient_html": "cases/p16_sections/recipient.html",
    "instruction_html": "cases/p16_sections/instruction.html",
    "copies_html": "cases/p16_sections/copies.html",
    "administration_legal_basis_html": "cases/p16_sections/administration_legal_basis.html",
    "administration_consideration_html": "cases/p16_sections/administration_consideration.html",
    "administration_instruction_html": "cases/p16_sections/administration_instruction.html",
    "administration_copies_html": "cases/p16_sections/administration_copies.html",
}


def build_default_p16_sections(draft):
    from configurations.models import InstitutionConfiguration
    from configurations.document_templates import render_configured_sections

    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    context = {
        "draft": draft,
        "assignment": draft.assignment,
        "spdp": draft.assignment.spdp,
        "institution": institution,
    }
    defaults = {
        field_name: sanitize_p16_html(render_to_string(template_name, context).strip())
        for field_name, template_name in SECTION_TEMPLATES.items()
    }
    return render_configured_sections("p16", defaults, context, sanitize_p16_html)


def ensure_p16_sections(draft):
    defaults = build_default_p16_sections(draft)
    changed_fields = []
    for field_name, default_value in defaults.items():
        if not getattr(draft, field_name) or (field_name == "subject" and draft.last_edited_by_id is None):
            setattr(draft, field_name, default_value)
            changed_fields.append(field_name)
    if changed_fields:
        draft.save(update_fields=(*changed_fields, "updated_at"))
    return changed_fields


def build_default_p16_content(draft):
    from configurations.models import InstitutionConfiguration

    institution = InstitutionConfiguration.objects.first() or InstitutionConfiguration()
    suspect_rows = []
    for suspect in draft.assignment.spdp.suspects.all():
        age = None
        if suspect.birth_date:
            on_date = draft.letter_date
            age = on_date.year - suspect.birth_date.year - ((on_date.month, on_date.day) < (suspect.birth_date.month, suspect.birth_date.day))
        suspect_rows.append({"suspect": suspect, "age": age})
    return render_to_string("cases/p16_default_content.html", {
        "draft": draft,
        "assignment": draft.assignment,
        "spdp": draft.assignment.spdp,
        "institution": institution,
        "suspect_rows": suspect_rows,
    }).strip()
