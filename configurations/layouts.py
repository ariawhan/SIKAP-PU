import math
from copy import deepcopy


FONT_CHOICES = {
    "arial": ("Arial", "Arial, sans-serif"),
    "times": ("Times New Roman", '"Times New Roman", Times, serif'),
    "calibri": ("Calibri", 'Calibri, "Segoe UI", sans-serif'),
}


P16_LAYOUT_GROUPS = (
    {
        "key": "page",
        "label": "Kertas & Margin",
        "description": "Atur ruang aman cetak dan tipografi dasar.",
        "fields": (
            ("margin_top_cm", "Margin atas", "cm", 0.5, 4, 0.1),
            ("margin_right_cm", "Margin kanan", "cm", 0.5, 4, 0.01),
            ("margin_bottom_cm", "Margin bawah", "cm", 0.8, 4, 0.1),
            ("margin_left_cm", "Margin kiri", "cm", 0.5, 4, 0.1),
            ("font_size_pt", "Ukuran huruf", "pt", 8, 14, 0.1),
            ("line_height", "Spasi baris", "×", 1, 2, 0.05),
        ),
    },
    {
        "key": "letterhead",
        "label": "Kop Surat",
        "description": "Sesuaikan logo, teks instansi, dan jarak kop.",
        "fields": (
            ("letterhead_height_cm", "Tinggi area kop", "cm", 1.8, 4, 0.01),
            ("letterhead_gap_pt", "Jarak setelah kop", "pt", 0, 30, 1),
            ("logo_width_cm", "Lebar logo", "cm", 1.5, 5, 0.05),
            ("logo_height_cm", "Tinggi logo", "cm", 1.5, 4, 0.05),
            ("logo_offset_x_cm", "Posisi logo X", "cm", -2, 2, 0.01),
            ("logo_offset_y_cm", "Posisi logo Y", "cm", -1.5, 1.5, 0.01),
            ("header_offset_x_cm", "Posisi teks kop X", "cm", -2, 2, 0.01),
            ("header_offset_y_cm", "Posisi teks kop Y", "cm", -1.5, 1.5, 0.01),
            ("header_font_size_pt", "Huruf kop", "pt", 8, 16, 0.1),
            ("address_font_size_pt", "Huruf alamat", "pt", 6, 12, 0.1),
        ),
    },
    {
        "key": "content",
        "label": "Isi Dokumen",
        "description": "Atur lebar label dan indentasi isi tanpa memutus pagination.",
        "fields": (
            ("clause_label_width_pt", "Lebar label bagian", "pt", 45, 110, 1),
            ("clause_colon_width_pt", "Lebar kolom titik dua", "pt", 6, 25, 1),
            ("body_indent_pt", "Indentasi uraian", "pt", 60, 180, 0.1),
            ("continuation_indent_pt", "Indentasi lanjutan", "pt", 40, 160, 0.1),
            ("suspect_indent_pt", "Indentasi data pelaku", "pt", 70, 210, 0.1),
            ("copies_top_pt", "Jarak atas tembusan", "pt", 0, 80, 1),
        ),
    },
    {
        "key": "signature",
        "label": "Tanda Tangan & TTE",
        "description": "Geser blok tanda tangan dan sesuaikan ukuran TTE.",
        "fields": (
            ("signature_width_pct", "Lebar blok", "%", 35, 80, 1),
            ("signature_top_pt", "Jarak dari isi", "pt", 0, 100, 1),
            ("signature_right_pt", "Jarak dari kanan", "pt", -20, 100, 1),
            ("tte_height_pt", "Tinggi gambar TTE", "pt", 20, 80, 1),
        ),
    },
    {
        "key": "barcode",
        "label": "Barcode / QR",
        "description": "Posisikan barcode di area margin bawah kertas.",
        "fields": (
            ("barcode_width_pt", "Lebar barcode", "pt", 20, 90, 0.1),
            ("barcode_height_pt", "Tinggi barcode", "pt", 20, 90, 0.1),
            ("barcode_offset_x_cm", "Posisi horizontal", "cm", -3, 3, 0.01),
            ("barcode_bottom_lift_mm", "Naik dari tengah margin", "mm", -10, 20, 0.1),
        ),
    },
)


P16_LAYOUT_DEFAULTS = {
    "font_family": "arial",
    "margin_top_cm": 1,
    "margin_right_cm": 2.09,
    "margin_bottom_cm": 2,
    "margin_left_cm": 2,
    "font_size_pt": 10,
    "line_height": 1.15,
    "letterhead_height_cm": 2.68,
    "letterhead_gap_pt": 9,
    "logo_width_cm": 3.35,
    "logo_height_cm": 2.68,
    "logo_offset_x_cm": -0.09,
    "logo_offset_y_cm": 0,
    "header_offset_x_cm": 0,
    "header_offset_y_cm": 0,
    "header_font_size_pt": 10,
    "address_font_size_pt": 8,
    "clause_label_width_pt": 68,
    "clause_colon_width_pt": 12,
    "body_indent_pt": 117.2,
    "continuation_indent_pt": 89.8,
    # Dengan kolom nomor 16pt pada blok identitas, nilai 88pt membuat awal
    # label sejajar dengan awal teks butir dasar (termasuk Surat Pemberitahuan).
    "suspect_indent_pt": 88,
    "copies_top_pt": 34,
    "signature_width_pct": 58,
    "signature_top_pt": 28,
    "signature_right_pt": 21,
    "tte_height_pt": 38,
    "barcode_width_pt": 38.4,
    "barcode_height_pt": 43.3,
    "barcode_offset_x_cm": -0.045,
    "barcode_bottom_lift_mm": 1.5,
}


P16_FIELD_SPECS = {
    key: {"label": label, "unit": unit, "min": minimum, "max": maximum, "step": step}
    for group in P16_LAYOUT_GROUPS
    for key, label, unit, minimum, maximum, step in group["fields"]
}


def default_document_layout(template_key="p16"):
    if template_key != "p16":
        raise ValueError("Template tata letak tidak dikenal.")
    return deepcopy(P16_LAYOUT_DEFAULTS)


def validate_document_layout(template_key, values, *, partial=False):
    if template_key != "p16":
        return default_document_layout("p16"), {"template": "Template tata letak tidak dikenal."}
    result = default_document_layout(template_key)
    errors = {}
    font_family = values.get("font_family", result["font_family"])
    if font_family not in FONT_CHOICES:
        errors["font_family"] = "Jenis huruf tidak didukung."
    else:
        result["font_family"] = font_family
    for key, spec in P16_FIELD_SPECS.items():
        raw = values.get(key, result[key])
        if partial and key not in values:
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError):
            errors[key] = "Masukkan angka yang valid."
            continue
        if not math.isfinite(number) or number < spec["min"] or number > spec["max"]:
            errors[key] = f"Nilai harus antara {spec['min']} dan {spec['max']} {spec['unit']}."
            continue
        result[key] = round(number, 3)
    return result, errors


def normalize_document_layout(template_key, settings):
    layout, _ = validate_document_layout(template_key, settings or {}, partial=True)
    return layout


def _number(value):
    return f"{float(value):.3f}".rstrip("0").rstrip(".")


def document_layout_style(template_key, layout):
    if template_key != "p16":
        return ""
    font_stack = FONT_CHOICES[layout["font_family"]][1]
    variables = {
        "--p16-font-family": font_stack,
        "--p16-margin-top": f"{_number(layout['margin_top_cm'])}cm",
        "--p16-margin-right": f"{_number(layout['margin_right_cm'])}cm",
        "--p16-margin-bottom": f"{_number(layout['margin_bottom_cm'])}cm",
        "--p16-margin-left": f"{_number(layout['margin_left_cm'])}cm",
        "--p16-font-size": f"{_number(layout['font_size_pt'])}pt",
        "--p16-line-height": _number(layout["line_height"]),
        "--p16-letterhead-height": f"{_number(layout['letterhead_height_cm'])}cm",
        "--p16-letterhead-gap": f"{_number(layout['letterhead_gap_pt'])}pt",
        "--p16-logo-width": f"{_number(layout['logo_width_cm'])}cm",
        "--p16-logo-height": f"{_number(layout['logo_height_cm'])}cm",
        "--p16-logo-offset-x": f"{_number(layout['logo_offset_x_cm'])}cm",
        "--p16-logo-offset-y": f"{_number(layout['logo_offset_y_cm'])}cm",
        "--p16-header-offset-x": f"{_number(layout['header_offset_x_cm'])}cm",
        "--p16-header-offset-y": f"{_number(layout['header_offset_y_cm'])}cm",
        "--p16-header-font-size": f"{_number(layout['header_font_size_pt'])}pt",
        "--p16-address-font-size": f"{_number(layout['address_font_size_pt'])}pt",
        "--p16-clause-label-width": f"{_number(layout['clause_label_width_pt'])}pt",
        "--p16-clause-colon-width": f"{_number(layout['clause_colon_width_pt'])}pt",
        "--p16-body-indent": f"{_number(layout['body_indent_pt'])}pt",
        "--p16-continuation-indent": f"{_number(layout['continuation_indent_pt'])}pt",
        "--p16-suspect-indent": f"{_number(layout['suspect_indent_pt'])}pt",
        "--p16-copies-top": f"{_number(layout['copies_top_pt'])}pt",
        "--p16-signature-width": f"{_number(layout['signature_width_pct'])}%",
        "--p16-signature-top": f"{_number(layout['signature_top_pt'])}pt",
        "--p16-signature-right": f"{_number(layout['signature_right_pt'])}pt",
        "--p16-tte-height": f"{_number(layout['tte_height_pt'])}pt",
        "--p16-barcode-width": f"{_number(layout['barcode_width_pt'])}pt",
        "--p16-barcode-height": f"{_number(layout['barcode_height_pt'])}pt",
        "--p16-barcode-offset-x": f"{_number(layout['barcode_offset_x_cm'])}cm",
        "--p16-barcode-bottom-lift": f"{_number(layout['barcode_bottom_lift_mm'])}mm",
    }
    return ";".join(f"{name}:{value}" for name, value in variables.items())


def layout_groups_with_values(layout, errors=None):
    errors = errors or {}
    groups = []
    for group in P16_LAYOUT_GROUPS:
        fields = []
        for key, label, unit, minimum, maximum, step in group["fields"]:
            fields.append({
                "key": key,
                "label": label,
                "unit": unit,
                "min": minimum,
                "max": maximum,
                "step": step,
                "value": layout[key],
                "error": errors.get(key, ""),
            })
        groups.append({**group, "fields": fields})
    return groups
