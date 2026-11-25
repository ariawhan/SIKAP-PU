from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "docs" / "Analisis_Sistem_Notifikasi_SIKAP_PU.docx"

MAROON = "7A1F2B"
LIGHT_MAROON = "F7E9EB"
LIGHT_GRAY = "F2F4F3"
TEXT_DARK = RGBColor(34, 41, 37)


def set_cell_shading(cell, fill):
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_width(cell, width_cm):
    cell.width = Cm(width_cm)
    properties = cell._tc.get_or_add_tcPr()
    tc_width = properties.find(qn("w:tcW"))
    if tc_width is None:
        tc_width = OxmlElement("w:tcW")
        properties.append(tc_width)
    tc_width.set(qn("w:w"), str(int(Cm(width_cm).emu / 635)))
    tc_width.set(qn("w:type"), "dxa")


def repeat_table_header(row):
    properties = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    properties.append(repeat)


def prevent_row_split(row):
    properties = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    properties.append(cant_split)


def set_cell_text(cell, text, *, bold=False, color=None, size=8.5, align=None):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    if align is not None:
        paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.05
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(document, headers, rows, widths):
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    table.autofit = False
    header = table.rows[0]
    repeat_table_header(header)
    for index, (label, width) in enumerate(zip(headers, widths)):
        set_cell_width(header.cells[index], width)
        set_cell_shading(header.cells[index], MAROON)
        set_cell_text(
            header.cells[index], label, bold=True, color="FFFFFF", size=8.5,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    for row_index, values in enumerate(rows, start=1):
        row = table.add_row()
        prevent_row_split(row)
        if row_index % 2 == 0:
            for cell in row.cells:
                set_cell_shading(cell, LIGHT_GRAY)
        for column_index, (value, width) in enumerate(zip(values, widths)):
            set_cell_width(row.cells[column_index], width)
            alignment = WD_ALIGN_PARAGRAPH.CENTER if column_index in (0, 2, 5) else WD_ALIGN_PARAGRAPH.LEFT
            set_cell_text(row.cells[column_index], value, size=8.2, align=alignment)
    return table


def add_heading(document, text, level=1):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(8 if level == 1 else 5)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(text)
    run.bold = True
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    run.font.size = Pt(13 if level == 1 else 10.5)
    run.font.color.rgb = RGBColor.from_string(MAROON)
    return paragraph


def add_body(document, text, *, bold_prefix=None):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.line_spacing = 1.08
    if bold_prefix and text.startswith(bold_prefix):
        first = paragraph.add_run(bold_prefix)
        first.bold = True
        remaining = paragraph.add_run(text[len(bold_prefix):])
        runs = (first, remaining)
    else:
        runs = (paragraph.add_run(text),)
    for run in runs:
        run.font.name = "Arial"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        run.font.size = Pt(9)
        run.font.color.rgb = TEXT_DARK
    return paragraph


def add_bullet(document, text):
    paragraph = document.add_paragraph(style="List Bullet")
    paragraph.paragraph_format.space_after = Pt(1.5)
    paragraph.paragraph_format.left_indent = Cm(0.55)
    paragraph.paragraph_format.first_line_indent = Cm(-0.25)
    run = paragraph.add_run(text)
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    run.font.size = Pt(8.8)
    return paragraph


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Halaman ")
    run.font.name = "Arial"
    run.font.size = Pt(8)
    field_begin = OxmlElement("w:fldChar")
    field_begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    field_end = OxmlElement("w:fldChar")
    field_end.set(qn("w:fldCharType"), "end")
    run._r.extend((field_begin, instruction, field_end))


def build_document():
    document = Document()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Cm(1.25)
    section.bottom_margin = Cm(1.25)
    section.left_margin = Cm(1.25)
    section.right_margin = Cm(1.25)
    section.header_distance = Cm(0.55)
    section.footer_distance = Cm(0.55)

    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.font.size = Pt(9)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(2)
    run = title.add_run("ANALISIS SISTEM NOTIFIKASI SIKAP-PU")
    run.bold = True
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    run.font.size = Pt(17)
    run.font.color.rgb = RGBColor.from_string(MAROON)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(8)
    run = subtitle.add_run("Hasil audit implementasi aplikasi per 24 November 2026 (WITA)")
    run.italic = True
    run.font.name = "Arial"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    run.font.size = Pt(9)

    add_heading(document, "1. Ringkasan Konfigurasi Aktif")
    config_rows = [
        ("Notifikasi otomatis", "Aktif", "Worker memeriksa reminder dan antrean setiap 30 detik."),
        ("Jam reminder otomatis", "10.00 WITA", "Reminder H otomatis dibuat setelah jam ini pada hari yang memenuhi jadwal."),
        ("WhatsApp", "Aktif", "Status gateway saat audit: aktif."),
        ("Telegram", "Aktif", "Menggunakan bot token dan Chat ID pengguna/default yang dikonfigurasi."),
        ("Jeda pesan eksternal", "2 menit per kanal", "Antrean WhatsApp dan Telegram dihitung terpisah; maksimal satu pesan jatuh tempo per kanal tiap pemeriksaan."),
        ("Kanal per menu", "Aplikasi + WhatsApp + Telegram", "Semua menu reminder yang sudah tersedia saat audit berada pada kondisi aktif."),
    ]
    add_table(document, ("Pengaturan", "Nilai Saat Audit", "Penjelasan"), config_rows, (4.0, 3.0, 19.0))

    add_heading(document, "2. Matriks Notifikasi Operasional")
    add_body(
        document,
        "Kolom Reminder menggunakan H sebagai tanggal jatuh tempo. H-2 berarti dua hari sebelum tenggat, H-1 satu hari sebelum tenggat, dan H adalah hari tenggat.",
    )
    rows = [
        (
            "1", "Penugasan Penunjukan Jaksa P-16",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum yang dipilih",
            "Saat petugas menekan Proses P-16 dan perkara diteruskan kepada Kasi Pidum. Notifikasi aplikasi dibuat langsung; WhatsApp/Telegram masuk antrean setelah transaksi tersimpan.",
            "-",
        ),
        (
            "2", "Reminder Penerbitan P-16 dari SPDP",
            "Aplikasi, WhatsApp, Telegram", "Kasubsi Prapenuntutan serta Kasi Pidum/Admin/Staf aktif; tim perkara ikut bila sudah terbentuk",
            "Otomatis mulai pukul 10.00 WITA pada hari reminder, atau kapan saja melalui tombol notifikasi manual. Tenggat 3 hari sejak SPDP diterima.",
            "H-2, H-1, H (hari ke-1, 2, 3)",
        ),
        (
            "3", "Reminder P-16",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum, Jaksa yang ditunjuk, petugas administrasi, Kasubsi Prapenuntutan",
            "Otomatis mulai pukul 10.00 WITA atau melalui tombol manual selama P-16 resmi masih menjadi tahap aktif. Tenggat 30 hari sejak P-16 terbit.",
            "H-2, H-1, H (hari ke-28, 29, 30)",
        ),
        (
            "4", "Reminder P-17",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum, Jaksa yang ditunjuk, petugas administrasi, Kasubsi Prapenuntutan",
            "Otomatis mulai pukul 10.00 WITA atau melalui tombol manual selama P-17 resmi masih menjadi tahap aktif. Tenggat 30 hari sejak P-17 terbit.",
            "H-2, H-1, H (hari ke-28, 29, 30)",
        ),
        (
            "5", "Reminder SOP Form 2",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum, Jaksa yang ditunjuk, petugas administrasi, Kasubsi Prapenuntutan",
            "Otomatis mulai pukul 10.00 WITA atau melalui tombol manual selama SOP Form 2 resmi masih menjadi tahap aktif. Tenggat 30 hari sejak SOP Form 2 terbit.",
            "H-2, H-1, H (hari ke-28, 29, 30)",
        ),
        (
            "6", "Reminder Tahap 1",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum, Jaksa yang ditunjuk, petugas administrasi, Kasubsi Prapenuntutan",
            "Otomatis mulai pukul 10.00 WITA atau melalui tombol manual. Tenggat 7 hari dihitung sejak data Tahap 1 disimpan/diselesaikan.",
            "H-2, H-1, H (hari ke-5, 6, 7)",
        ),
        (
            "7", "Reminder P-19",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum, Jaksa yang ditunjuk, petugas administrasi, Kasubsi Prapenuntutan",
            "Otomatis mulai pukul 10.00 WITA atau melalui tombol manual selama P-19 resmi masih menjadi tahap aktif. Tenggat 14 hari sejak P-19 terbit.",
            "H-2, H-1, H (hari ke-12, 13, 14)",
        ),
        (
            "8", "Reminder P-21",
            "Aplikasi, WhatsApp, Telegram", "Kasi Pidum, Jaksa yang ditunjuk, petugas administrasi, Kasubsi Prapenuntutan",
            "Otomatis mulai pukul 10.00 WITA atau melalui tombol manual selama P-21 resmi belum ditandai dilaksanakan. Tenggat 14 hari sejak P-21 terbit.",
            "H-2, H-1, H (hari ke-12, 13, 14)",
        ),
        (
            "9", "SOP Form 3 Terbit",
            "WhatsApp, Telegram", "Pembuat draf, Kasi Pidum, Jaksa yang ditunjuk, dan petugas administrasi",
            "Setelah SOP Form 3 berhasil diunggah ke SIPede dan transaksi penyimpanan selesai. Implementasi saat ini tidak membuat notifikasi lonceng aplikasi.",
            "-",
        ),
        (
            "10", "WhatsApp Gateway Logout / Perlu Login Ulang",
            "Telegram", "Chat ID Telegram admin/default",
            "Langsung setelah logout manual, atau ketika monitor (cek tiap 5 menit) mendeteksi gateway tidak aktif. Selama masih terputus, alert dapat diulang setiap 60 menit.",
            "- (pengulangan waktu, bukan H-reminder)",
        ),
        (
            "11", "WhatsApp Gateway Aktif Kembali",
            "Telegram", "Chat ID Telegram admin/default",
            "Sekali ketika monitor mendeteksi perubahan status dari tidak aktif menjadi aktif kembali; umumnya paling lambat pada siklus cek 5 menit berikutnya.",
            "-",
        ),
        (
            "12", "Pesan Tes WhatsApp",
            "WhatsApp", "Nomor uji gateway",
            "Saat Super Admin menekan tombol tes pesan WhatsApp pada menu Notifikasi. Digunakan untuk diagnostik, bukan alur perkara.",
            "-",
        ),
        (
            "13", "Pesan Tes Telegram",
            "Telegram", "Chat ID yang diisi atau Chat ID default",
            "Saat Super Admin menekan tombol tes Telegram pada menu Notifikasi. Digunakan untuk diagnostik, bukan alur perkara.",
            "-",
        ),
        (
            "14", "Balasan Registrasi /start Telegram",
            "Telegram", "Pengguna/chat yang mengirim /start",
            "Langsung ketika bot menerima perintah /start. Jika username/email disertakan dan cocok, Chat ID dihubungkan ke akun pengguna.",
            "-",
        ),
    ]
    add_table(
        document,
        ("No.", "Nama Notifikasi", "Jenis/Kanal", "Penerima", "Kapan Dinotifikasi", "Reminder"),
        rows,
        (0.7, 4.2, 3.0, 4.7, 10.5, 3.9),
    )

    add_heading(document, "3. Tahapan yang Tidak Memiliki Reminder Tenggat Otomatis")
    no_reminder_rows = [
        ("P-18", "Tidak ada reminder", "Ketika P-18 menjadi tahap aktif, mesin tenggat menghentikan reminder sampai alur berikutnya dibentuk."),
        ("P-20", "Tidak ada reminder", "P-20 diperlakukan sebagai penutup alur reminder P-19."),
        ("SOP Form 3", "Tidak ada reminder tenggat", "Hanya memiliki notifikasi terbit melalui WhatsApp dan Telegram setelah upload SIPede."),
        ("SOP Form 7", "Tidak ada reminder", "SOP Form 7 menutup alur reminder setelah P-21."),
        ("SOP Form 1B", "Tidak ada notifikasi khusus", "Dokumen berada di menu P-17 tetapi tidak mempunyai pemicu notifikasi tersendiri."),
        ("Berita Acara Koordinasi 1-3", "Tidak ada notifikasi khusus", "Belum terdaftar dalam menu/tahap notifikasi."),
    ]
    add_table(document, ("Menu/Tahap", "Status", "Analisis"), no_reminder_rows, (5.0, 5.0, 17.0))

    add_heading(document, "4. Catatan Perilaku Sistem")
    notes = [
        "Reminder otomatis hanya dibuat tepat pada H-2, H-1, dan H. Setelah melewati H, sistem tidak mengirim pengulangan otomatis tambahan.",
        "Tombol notifikasi manual dapat mengirim reminder tahap aktif di luar jadwal H-2/H-1/H dan tidak memakai pembatas unik pengiriman otomatis.",
        "Setiap kombinasi perkara, tahap, dokumen, dan hari reminder otomatis dicatat satu kali agar tidak diduplikasi pada hari yang sama.",
        "Notifikasi aplikasi dibuat langsung. WhatsApp dan Telegram masuk antrean dengan jeda minimum dua menit untuk masing-masing kanal.",
        "Jika nomor WhatsApp atau Chat ID Telegram penerima kosong, log dibuat dengan status Gagal dan alasan kekurangan data tujuan.",
        "Ketika tahap berikutnya resmi terbit atau Tahap 1 disimpan, notifikasi aplikasi yang terkait perkara ditutup/dihapus. Antrean P-21 juga dibatalkan ketika P-21 ditandai sudah dilaksanakan.",
        "Pengiriman tiap menu tetap mengikuti centang kanal pada Konfigurasi Notifikasi dan status global WhatsApp/Telegram.",
        "Sumber audit: cases/reminders.py, notifications/services.py, notifications/template_defaults.py, notifications/models.py, cases/views.py, dashboard/views.py, dan worker pada scripts/start_background_workers.ps1.",
    ]
    for note in notes:
        add_bullet(document, note)

    footer = section.footer.paragraphs[0]
    add_page_number(footer)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT_PATH)
    return OUTPUT_PATH


if __name__ == "__main__":
    path = build_document()
    print(path)
