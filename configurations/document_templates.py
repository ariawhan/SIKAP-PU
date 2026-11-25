from collections import OrderedDict

from django.template import TemplateSyntaxError, engines
from django.template.loader import get_template

from .models import DocumentTemplateConfiguration


DOCUMENT_TEMPLATES = OrderedDict([
    ("p16", {
        "label": "P-16",
        "description": "Surat P-16, lampiran, dan penunjukan petugas administrasi.",
        "sections": (
            ("subject", "Perihal", "cases/p16_sections/subject.html"),
            ("consideration_html", "Menimbang", "cases/p16_sections/consideration.html"),
            ("legal_basis_html", "Dasar", "cases/p16_sections/legal_basis.html"),
            ("offense_summary_html", "Uraian tindak pidana", "cases/p16_sections/offense_summary.html"),
            ("recipient_html", "Kepada", "cases/p16_sections/recipient.html"),
            ("instruction_html", "Untuk", "cases/p16_sections/instruction.html"),
            ("copies_html", "Tembusan", "cases/p16_sections/copies.html"),
            ("administration_legal_basis_html", "Administrasi · Dasar", "cases/p16_sections/administration_legal_basis.html"),
            ("administration_consideration_html", "Administrasi · Menimbang", "cases/p16_sections/administration_consideration.html"),
            ("administration_instruction_html", "Administrasi · Untuk", "cases/p16_sections/administration_instruction.html"),
            ("administration_copies_html", "Administrasi · Tembusan", "cases/p16_sections/administration_copies.html"),
        ),
    }),
    ("p17", {
        "label": "P-17",
        "description": "Permintaan perkembangan hasil penyidikan.",
        "sections": (
            ("subject_html", "Perihal", "cases/p17_sections/subject.html"),
            ("body_html", "Isi", "cases/p17_sections/body.html"),
            ("copies_html", "Tembusan", "cases/p17_sections/copies.html"),
        ),
    }),
    ("sop1b", {
        "label": "SOP Form-1B",
        "description": "Laporan Penuntut Umum pada menu P-17.",
        "sections": (
            ("legal_basis_html", "I. Dasar", "cases/sop_form_1b_sections/legal_basis.html"),
            ("facts_html", "II. Fakta dan Data", "cases/sop_form_1b_sections/facts.html"),
            ("legal_analysis_html", "III. Analisis Yuridis", "cases/sop_form_1b_sections/legal_analysis.html"),
            ("conclusion_html", "IV. Kesimpulan dan Saran", "cases/sop_form_1b_sections/conclusion.html"),
        ),
    }),
    ("sop02", {
        "label": "SOP Form-2",
        "description": "Template generate SOP Form-2.",
        "sections": (
            ("subject_html", "Perihal", "cases/sop_form_02_sections/subject.html"),
            ("body_html", "Isi", "cases/sop_form_02_sections/body.html"),
            ("copies_html", "Tembusan", "cases/sop_form_02_sections/copies.html"),
        ),
    }),
    ("sop03", {
        "label": "SOP Form-3",
        "description": "Template generate SOP Form-3.",
        "sections": (
            ("subject_html", "Perihal", "cases/sop_form_03_sections/subject.html"),
            ("body_html", "Isi", "cases/sop_form_03_sections/body.html"),
            ("copies_html", "Tembusan", "cases/sop_form_03_sections/copies.html"),
        ),
    }),
    ("p18", {
        "label": "P-18", "description": "Surat hasil penelitian berkas belum lengkap.",
        "sections": tuple((f"{name}_html", label, f"cases/case_document_sections/p18_{name}.html") for name, label in (("subject", "Perihal"), ("legal_basis", "Dasar"), ("body", "Isi"), ("copies", "Tembusan"))),
    }),
    ("p19", {
        "label": "P-19", "description": "Surat pengembalian berkas dan petunjuk.",
        "sections": (
            ("subject_html", "Perihal", "cases/case_document_sections/p19_subject.html"),
            ("legal_basis_html", "Dasar (bawaan kosong)", None),
            ("body_html", "Isi (bawaan kosong)", None),
            ("copies_html", "Tembusan", "cases/case_document_sections/p19_copies.html"),
        ),
    }),
    ("p20", {
        "label": "P-20", "description": "Pemberitahuan berakhirnya waktu penyidikan tambahan.",
        "sections": tuple((f"{name}_html", label, f"cases/case_document_sections/p20_{name}.html") for name, label in (("subject", "Perihal"), ("legal_basis", "Dasar"), ("body", "Isi"), ("copies", "Tembusan"))),
    }),
    ("p21", {
        "label": "P-21", "description": "Pemberitahuan hasil penyidikan sudah lengkap.",
        "sections": tuple((f"{name}_html", label, f"cases/p21_sections/{name}.html") for name, label in (("subject", "Perihal"), ("legal_basis", "Dasar"), ("body", "Isi"), ("copies", "Tembusan"))),
    }),
    ("sop07", {
        "label": "SOP Form-7", "description": "Pengembalian SPDP dan berkas setelah P-21.",
        "sections": tuple((f"{name}_html", label, f"cases/case_document_sections/sop07_{name}.html") for name, label in (("subject", "Perihal"), ("legal_basis", "Dasar"), ("body", "Isi"), ("copies", "Tembusan"))),
    }),
])


def definition_for(template_key):
    return DOCUMENT_TEMPLATES.get(template_key)


def _source_from_file(template_name):
    if not template_name:
        return ""
    template = get_template(template_name)
    return template.template.source.strip()


def default_sources(template_key):
    definition = definition_for(template_key)
    if not definition:
        return {}
    return {
        field_name: _source_from_file(template_name)
        for field_name, _label, template_name in definition["sections"]
    }


def validate_sources(template_key, sources):
    definition = definition_for(template_key)
    if not definition:
        return {"template_key": "Menu dokumen tidak dikenal."}
    allowed = {field_name for field_name, _label, _template in definition["sections"]}
    errors = {}
    engine = engines["django"]
    for field_name, source in sources.items():
        if field_name not in allowed:
            continue
        if len(source) > 100_000:
            errors[field_name] = "Template maksimal 100.000 karakter."
            continue
        try:
            engine.from_string(source)
        except TemplateSyntaxError as exc:
            errors[field_name] = f"Sintaks template tidak valid: {exc}"
    return errors


def configured_sources(template_key):
    configuration = DocumentTemplateConfiguration.objects.filter(template_key=template_key).first()
    return configuration.sections if configuration else {}


def render_configured_sections(template_key, defaults, context, sanitizer=None):
    """Overlay template tersimpan pada hasil bawaan generator.

    Sumber kosong berarti bagian memang dikosongkan. Jika belum ada konfigurasi,
    seluruh hasil generator lama dipertahankan.
    """
    configuration = DocumentTemplateConfiguration.objects.filter(template_key=template_key).first()
    if not configuration:
        return defaults
    definition = definition_for(template_key)
    if not definition:
        return defaults
    result = dict(defaults)
    engine = engines["django"]
    for field_name, _label, _template in definition["sections"]:
        if field_name not in configuration.sections:
            continue
        source = str(configuration.sections.get(field_name, ""))
        try:
            rendered = engine.from_string(source).render(context).strip()
        except Exception:
            continue
        result[field_name] = sanitizer(rendered) if sanitizer else rendered
    return result


def template_rows(template_key, values=None, errors=None):
    definition = definition_for(template_key)
    defaults = default_sources(template_key)
    values = values or configured_sources(template_key)
    errors = errors or {}
    rows = []
    for field_name, label, _template in definition["sections"]:
        rows.append({
            "field_name": field_name,
            "label": label,
            "value": values[field_name] if field_name in values else defaults.get(field_name, ""),
            "error": errors.get(field_name, ""),
            "customized": field_name in values,
        })
    return rows
