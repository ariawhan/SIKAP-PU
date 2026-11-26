"""Template notifikasi bawaan SIKAP-PU dan variabel yang diizinkan."""

APP_NAME = "SIKAP-PU"

CASE_DETAIL_BLOCK = (
    "\n\nData penanganan perkara:\n"
    "Pelaku / terlapor    : {daftar_pelaku}\n"
    "Jaksa yang menangani : {daftar_jaksa}\n"
    "Petugas administrasi : {daftar_pegawai}"
)
CASE_DETAIL_VARIABLES = ("daftar_pelaku", "daftar_jaksa", "daftar_pegawai")

TEMPLATE_DEFINITIONS = {
    "p16_assignment_web": {
        "name": "Penunjukan Jaksa P-16 - Aplikasi Web",
        "description": "Notifikasi pada lonceng aplikasi untuk Kasi Pidum ketika SPDP diteruskan.",
        "channel": "web",
        "subject": "Tugas Penunjukan Jaksa P-16",
        "body": (
            "SPDP {nomor_spdp} menunggu penunjukan Jaksa. "
            "Batas penerbitan P-16 {batas_p16} ({status_waktu})."
        ) + CASE_DETAIL_BLOCK,
        "variables": (
            "nama_aplikasi", "nama_penerima", "nomor_spdp", "tanggal_diterima",
            "jumlah_pelaku", "batas_p16", "status_waktu", "diteruskan_oleh",
        ) + CASE_DETAIL_VARIABLES,
    },
    "p16_assignment_whatsapp": {
        "name": "Penunjukan Jaksa P-16 - WhatsApp",
        "description": "Pesan WhatsApp kepada Kasi Pidum ketika SPDP diteruskan.",
        "channel": "whatsapp",
        "subject": "Tugas Penunjukan Jaksa P-16",
        "body": (
            "{nama_aplikasi} | TUGAS PENUNJUKAN JAKSA P-16\n\n"
            "Yth. Bapak/Ibu {nama_penerima},\n"
            "Satu perkara telah diteruskan kepada Anda dan memerlukan penunjukan Jaksa Penuntut Umum.\n\n"
            "Nomor SPDP       : {nomor_spdp}\n"
            "Tanggal diterima : {tanggal_diterima}\n"
            "Data pelaku      : {jumlah_pelaku}\n"
            "Batas P-16       : {batas_p16}\n"
            "Status waktu     : {status_waktu}\n\n"
            "Silakan masuk ke {nama_aplikasi}, buka Data Perkara, lalu pilih aksi Tunjuk Jaksa.\n\n"
            "Diteruskan oleh: {diteruskan_oleh}"
        ) + CASE_DETAIL_BLOCK,
        "variables": (
            "nama_aplikasi", "nama_penerima", "nomor_spdp", "tanggal_diterima",
            "jumlah_pelaku", "batas_p16", "status_waktu", "diteruskan_oleh",
        ) + CASE_DETAIL_VARIABLES,
    },
    "p16_assignment_telegram": {
        "name": "Penunjukan Jaksa P-16 - Telegram",
        "description": "Pesan Telegram kepada Kasi Pidum ketika SPDP diteruskan.",
        "channel": "telegram",
        "subject": "Tugas Penunjukan Jaksa P-16",
        "body": (
            "{nama_aplikasi} | TUGAS PENUNJUKAN JAKSA P-16\n\n"
            "Yth. Bapak/Ibu {nama_penerima},\n"
            "Satu perkara telah diteruskan kepada Anda dan memerlukan penunjukan Jaksa Penuntut Umum.\n\n"
            "Nomor SPDP       : {nomor_spdp}\n"
            "Tanggal diterima : {tanggal_diterima}\n"
            "Data pelaku      : {jumlah_pelaku}\n"
            "Batas P-16       : {batas_p16}\n"
            "Status waktu     : {status_waktu}\n\n"
            "Silakan masuk ke {nama_aplikasi}, buka Data Perkara, lalu pilih aksi Tunjuk Jaksa.\n\n"
            "Diteruskan oleh: {diteruskan_oleh}"
        ) + CASE_DETAIL_BLOCK,
        "variables": (
            "nama_aplikasi", "nama_penerima", "nomor_spdp", "tanggal_diterima",
            "jumlah_pelaku", "batas_p16", "status_waktu", "diteruskan_oleh",
        ) + CASE_DETAIL_VARIABLES,
    },
    "p16_investigator_issued_whatsapp": {
        "name": "P-16 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat P-16 perkara terbit.",
        "channel": "whatsapp",
        "subject": "P-16 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI P-16 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa surat P-16 untuk perkara yang Saudara tangani "
            "telah diterbitkan.\n\n"
            "Nomor P-16 : {nomor_surat}\n"
            "Nomor SPDP : {nomor_spdp}\n"
            "Tanggal    : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon berkoordinasi dengan Jaksa Penuntut Umum tersebut untuk perkembangan "
            "penyidikan perkara."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "p16",
    },
    "p17_investigator_issued_whatsapp": {
        "name": "P-17 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat P-17 perkara terbit.",
        "channel": "whatsapp",
        "subject": "P-17 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI P-17 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa surat P-17 untuk perkara yang Saudara tangani "
            "telah diterbitkan.\n\n"
            "Nomor P-17 : {nomor_surat}\n"
            "Nomor SPDP : {nomor_spdp}\n"
            "Tanggal    : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon menyampaikan perkembangan hasil penyidikan dan berkoordinasi dengan "
            "Jaksa Penuntut Umum yang menangani perkara."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "p17",
    },
    "sop02_investigator_issued_whatsapp": {
        "name": "SOP Form 2 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat SOP Form 2 perkara terbit.",
        "channel": "whatsapp",
        "subject": "SOP Form 2 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI SOP FORM 2 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa SOP Form 2 untuk perkara yang Saudara tangani "
            "telah diterbitkan.\n\n"
            "Nomor surat : {nomor_surat}\n"
            "Nomor SPDP  : {nomor_spdp}\n"
            "Tanggal     : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon menindaklanjuti surat tersebut dan berkoordinasi dengan Jaksa Penuntut "
            "Umum yang menangani perkara."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "sop02",
    },
    "sop03_investigator_issued_whatsapp": {
        "name": "SOP Form 3 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat SOP Form 3 perkara terbit.",
        "channel": "whatsapp",
        "subject": "SOP Form 3 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI SOP FORM 3 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa SOP Form 3 untuk perkara yang Saudara tangani "
            "telah diterbitkan.\n\n"
            "Nomor surat : {nomor_surat}\n"
            "Nomor SPDP  : {nomor_spdp}\n"
            "Tanggal     : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon memperhatikan dan menindaklanjuti surat tersebut sesuai penanganan perkara."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "sop03",
    },
    "p21_investigator_issued_whatsapp": {
        "name": "P-21 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat P-21 perkara terbit.",
        "channel": "whatsapp",
        "subject": "P-21 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI P-21 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa surat P-21 untuk perkara yang Saudara tangani "
            "telah diterbitkan dan hasil penyidikan telah dinyatakan lengkap.\n\n"
            "Nomor P-21 : {nomor_surat}\n"
            "Nomor SPDP : {nomor_spdp}\n"
            "Tanggal    : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon berkoordinasi dengan Jaksa Penuntut Umum untuk tindak lanjut penyerahan "
            "tersangka dan barang bukti."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "p21",
    },
    "p18_investigator_issued_whatsapp": {
        "name": "P-18 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat P-18 perkara terbit.",
        "channel": "whatsapp",
        "subject": "P-18 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI P-18 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa surat P-18 untuk perkara yang Saudara tangani "
            "telah diterbitkan. Hasil penyidikan dinyatakan belum lengkap.\n\n"
            "Nomor P-18 : {nomor_surat}\n"
            "Nomor SPDP : {nomor_spdp}\n"
            "Tanggal    : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon berkoordinasi dengan Jaksa Penuntut Umum dan menindaklanjuti petunjuk "
            "kelengkapan berkas perkara."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "p18",
    },
    "p19_investigator_issued_whatsapp": {
        "name": "P-19 Terbit untuk Penyidik - WhatsApp",
        "description": "Pesan khusus kepada penyidik saat P-19 perkara terbit.",
        "channel": "whatsapp",
        "subject": "P-19 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | INFORMASI P-19 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penyidik},\n"
            "Kami informasikan bahwa surat P-19 berisi petunjuk kelengkapan berkas untuk "
            "perkara yang Saudara tangani telah diterbitkan.\n\n"
            "Nomor P-19 : {nomor_surat}\n"
            "Nomor SPDP : {nomor_spdp}\n"
            "Tanggal    : {tanggal_surat}\n\n"
            "Tersangka / terlapor:\n{daftar_pelaku}\n\n"
            "Jaksa Penuntut Umum yang menangani:\n{daftar_jaksa}\n\n"
            "Mohon menindaklanjuti petunjuk formil dan materiil serta berkoordinasi dengan "
            "Jaksa Penuntut Umum sebelum berkas diserahkan kembali."
        ),
        "variables": (
            "nama_aplikasi", "nama_penyidik", "nomor_surat", "nomor_spdp",
            "tanggal_surat", "daftar_pelaku", "daftar_jaksa",
        ),
        "menu_key": "p19",
    },
    "sop_form_03_issued_whatsapp": {
        "name": "SOP Form 3 Terbit - WhatsApp",
        "description": "Notifikasi WhatsApp saat SOP Form 3 berstatus terbit.",
        "channel": "whatsapp",
        "subject": "SOP Form 3 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | SOP FORM 3 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penerima},\n"
            "SOP Form 3 telah berstatus terbit.\n\n"
            "Nomor SOP Form 3 : {nomor_surat}\n"
            "Nomor SPDP       : {nomor_spdp}\n"
            "Tanggal surat    : {tanggal_surat}"
        ) + CASE_DETAIL_BLOCK,
        "variables": (
            "nama_aplikasi", "nama_penerima", "nomor_surat", "nomor_spdp",
            "tanggal_surat",
        ) + CASE_DETAIL_VARIABLES,
    },
    "sop_form_03_issued_telegram": {
        "name": "SOP Form 3 Terbit - Telegram",
        "description": "Notifikasi Telegram saat SOP Form 3 berstatus terbit.",
        "channel": "telegram",
        "subject": "SOP Form 3 Terbit - {nomor_spdp}",
        "body": (
            "{nama_aplikasi} | SOP FORM 3 TERBIT\n\n"
            "Yth. Bapak/Ibu {nama_penerima},\n"
            "SOP Form 3 telah berstatus terbit.\n\n"
            "Nomor SOP Form 3 : {nomor_surat}\n"
            "Nomor SPDP       : {nomor_spdp}\n"
            "Tanggal surat    : {tanggal_surat}"
        ) + CASE_DETAIL_BLOCK,
        "variables": (
            "nama_aplikasi", "nama_penerima", "nomor_surat", "nomor_spdp",
            "tanggal_surat",
        ) + CASE_DETAIL_VARIABLES,
    },
    "case_deadline_web": {
        "name": "Reminder Tenggat Perkara - Aplikasi Web",
        "description": "Reminder tenggat tiga hari terakhir pada setiap tahapan perkara.",
        "channel": "web",
        "subject": "Reminder {tahapan} Hari ke-{hari_ke}",
        "body": "Perkara {nomor_spdp} pada {tahapan} telah {status_waktu}. Batas {masa_hari} hari: {tanggal_batas}. {tindak_lanjut}" + CASE_DETAIL_BLOCK,
        "variables": ("nama_aplikasi", "nama_penerima", "tahapan", "hari_ke", "nomor_spdp", "nomor_surat", "tanggal_surat", "tanggal_batas", "masa_hari", "status_waktu", "tindak_lanjut") + CASE_DETAIL_VARIABLES,
    },
    "case_deadline_whatsapp": {
        "name": "Reminder Tenggat Perkara - WhatsApp",
        "description": "Reminder tenggat tiga hari terakhir melalui WhatsApp.",
        "channel": "whatsapp",
        "subject": "Reminder {tahapan} Hari ke-{hari_ke}",
        "body": (
            "{nama_aplikasi} | REMINDER {tahapan}\n\nYth. Bapak/Ibu {nama_penerima},\n"
            "Perkara {nomor_spdp} telah memasuki hari ke-{hari_ke}.\n\n"
            "Nomor surat : {nomor_surat}\nTanggal surat: {tanggal_surat}\n"
            "Batas {masa_hari} hari: {tanggal_batas}\nStatus: {status_waktu}\n\n"
            "{tindak_lanjut}"
        ) + CASE_DETAIL_BLOCK,
        "variables": ("nama_aplikasi", "nama_penerima", "tahapan", "hari_ke", "nomor_spdp", "nomor_surat", "tanggal_surat", "tanggal_batas", "masa_hari", "status_waktu", "tindak_lanjut") + CASE_DETAIL_VARIABLES,
    },
    "case_deadline_telegram": {
        "name": "Reminder Tenggat Perkara - Telegram",
        "description": "Reminder tenggat tiga hari terakhir melalui Telegram.",
        "channel": "telegram",
        "subject": "Reminder {tahapan} Hari ke-{hari_ke}",
        "body": (
            "{nama_aplikasi} | REMINDER {tahapan}\n\nYth. Bapak/Ibu {nama_penerima},\n"
            "Perkara {nomor_spdp} telah memasuki hari ke-{hari_ke}.\n\n"
            "Nomor surat : {nomor_surat}\nTanggal surat: {tanggal_surat}\n"
            "Batas {masa_hari} hari: {tanggal_batas}\nStatus: {status_waktu}\n\n"
            "{tindak_lanjut}"
        ) + CASE_DETAIL_BLOCK,
        "variables": ("nama_aplikasi", "nama_penerima", "tahapan", "hari_ke", "nomor_spdp", "nomor_surat", "tanggal_surat", "tanggal_batas", "masa_hari", "status_waktu", "tindak_lanjut") + CASE_DETAIL_VARIABLES,
    },
    "whatsapp_logout_telegram": {
        "name": "WhatsApp Logout - Telegram Admin",
        "description": "Peringatan Telegram kepada admin ketika sesi WhatsApp terputus atau logout.",
        "channel": "telegram",
        "subject": "WhatsApp Gateway Perlu Login Ulang",
        "body": (
            "Peringatan {nama_aplikasi}\n\n"
            "Session WhatsApp Gateway {status_session}.\n"
            "Silakan buka menu Notifikasi dan scan ulang barcode WhatsApp.\n\n"
            "Oleh: {oleh}\n"
            "Waktu: {waktu} WITA"
        ),
        "variables": ("nama_aplikasi", "status_session", "oleh", "waktu"),
    },
    "whatsapp_recovered_telegram": {
        "name": "WhatsApp Aktif Kembali - Telegram Admin",
        "description": "Informasi Telegram kepada admin ketika sesi WhatsApp kembali aktif.",
        "channel": "telegram",
        "subject": "WhatsApp Gateway Aktif Kembali",
        "body": (
            "Info {nama_aplikasi}\n\n"
            "Session WhatsApp Gateway sudah aktif kembali.\n\n"
            "Waktu: {waktu} WITA"
        ),
        "variables": ("nama_aplikasi", "waktu"),
    },
}


DEADLINE_TEMPLATE_STAGES = {
    "spdp": "Data Perkara / SPDP",
    "p16": "P-16",
    "p17": "P-17",
    "sop02": "SOP Form 2",
    "stage1": "Tahap 1",
    "p19": "P-19",
    "p21": "P-21",
}

DOCUMENT_ISSUED_STAGES = {
    "p16": "P-16",
    "p17": "P-17",
    "sop02": "SOP Form 2",
    "sop03": "SOP Form 3",
    "stage1": "Tahap 1",
    "p18": "P-18",
    "p19": "P-19",
    "p20": "P-20",
    "p21": "P-21",
    "sop07": "SOP Form 7",
}

# Penunjukan P-16 menggunakan konfigurasi kanal menu P-16 yang sama.
for assignment_key in (
    "p16_assignment_web",
    "p16_assignment_whatsapp",
    "p16_assignment_telegram",
):
    TEMPLATE_DEFINITIONS[assignment_key]["menu_key"] = "p16"

for channel in ("whatsapp", "telegram"):
    TEMPLATE_DEFINITIONS[f"sop_form_03_issued_{channel}"]["menu_key"] = "sop03"

# Penyidik memiliki template Telegram tersendiri. Isi awal mengikuti pesan
# WhatsApp, tetapi dapat disunting secara terpisah melalui konfigurasi notifikasi.
for _investigator_stage in ("p16", "p17", "sop02", "sop03", "p18", "p19", "p21"):
    _whatsapp_key = f"{_investigator_stage}_investigator_issued_whatsapp"
    _telegram_key = f"{_investigator_stage}_investigator_issued_telegram"
    _whatsapp_definition = TEMPLATE_DEFINITIONS[_whatsapp_key]
    _stage_label = DOCUMENT_ISSUED_STAGES[_investigator_stage]
    TEMPLATE_DEFINITIONS[_telegram_key] = {
        **_whatsapp_definition,
        "name": f"{_stage_label} Terbit untuk Penyidik - Telegram",
        "description": f"Pesan khusus Telegram kepada penyidik saat {_stage_label} perkara terbit.",
        "channel": "telegram",
    }


def issued_template_key(stage_key, channel):
    # Pertahankan kode template SOP Form 3 yang sudah digunakan pada instalasi lama.
    if stage_key == "sop03" and channel in ("whatsapp", "telegram"):
        return f"sop_form_03_issued_{channel}"
    return f"{stage_key}_issued_{channel}"


_issued_channel_labels = {
    "web": "Aplikasi Web",
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
}
for stage_key, stage_label in DOCUMENT_ISSUED_STAGES.items():
    for channel, channel_label in _issued_channel_labels.items():
        key = issued_template_key(stage_key, channel)
        if key in TEMPLATE_DEFINITIONS:
            continue
        if channel == "web":
            body = (
                "{tahapan} nomor {nomor_surat} untuk perkara {nomor_spdp} "
                "telah berstatus terbit pada {tanggal_surat}."
            ) + CASE_DETAIL_BLOCK
        else:
            body = (
                "{nama_aplikasi} | {tahapan} TERBIT\n\n"
                "Yth. Bapak/Ibu {nama_penerima},\n"
                "{tahapan} untuk perkara yang Anda tangani telah berstatus terbit.\n\n"
                "Nomor surat : {nomor_surat}\n"
                "Nomor SPDP  : {nomor_spdp}\n"
                "Tanggal     : {tanggal_surat}"
            ) + CASE_DETAIL_BLOCK
        TEMPLATE_DEFINITIONS[key] = {
            "name": f"{stage_label} Terbit - {channel_label}",
            "description": (
                f"Notifikasi {channel_label} kepada tim perkara saat {stage_label} terbit."
            ),
            "channel": channel,
            "subject": f"{stage_label} Terbit - {{nomor_spdp}}",
            "body": body,
            "variables": (
                "nama_aplikasi", "nama_penerima", "tahapan", "nomor_surat",
                "nomor_spdp", "tanggal_surat",
            ) + CASE_DETAIL_VARIABLES,
            "menu_key": stage_key,
        }

# Pecah template reminder generik menjadi template lengkap per tahap dan kanal.
_deadline_bases = {
    channel: TEMPLATE_DEFINITIONS.pop(f"case_deadline_{channel}")
    for channel in ("web", "whatsapp", "telegram")
}
for stage_key, stage_label in DEADLINE_TEMPLATE_STAGES.items():
    for channel, base_definition in _deadline_bases.items():
        definition = dict(base_definition)
        channel_label = {
            "web": "Aplikasi Web",
            "whatsapp": "WhatsApp",
            "telegram": "Telegram",
        }[channel]
        definition["name"] = f"{stage_label} - {channel_label}"
        definition["description"] = (
            f"Template reminder {stage_label} melalui {channel_label}."
        )
        definition["menu_key"] = stage_key
        TEMPLATE_DEFINITIONS[f"{stage_key}_deadline_{channel}"] = definition


def template_definition(key):
    return TEMPLATE_DEFINITIONS.get(key)
