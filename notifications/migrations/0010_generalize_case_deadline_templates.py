from django.db import migrations


OLD_WEB = "Perkara {nomor_spdp} berdasarkan {nomor_surat} telah {status_waktu}. Batas 30 hari: {tanggal_batas}."
NEW_WEB = "Perkara {nomor_spdp} pada {tahapan} telah {status_waktu}. Batas {masa_hari} hari: {tanggal_batas}. {tindak_lanjut}"

OLD_CHANNEL = (
    "{nama_aplikasi} | REMINDER {tahapan}\n\nYth. Bapak/Ibu {nama_penerima},\n"
    "Perkara {nomor_spdp} telah memasuki hari ke-{hari_ke}.\n\n"
    "Nomor surat : {nomor_surat}\nTanggal surat: {tanggal_surat}\n"
    "Batas 30 hari: {tanggal_batas}\nStatus: {status_waktu}\n\n"
    "Segera tindak lanjuti perkara atau input Tahap 1 apabila berkas perkara telah diterima."
)
NEW_CHANNEL = (
    "{nama_aplikasi} | REMINDER {tahapan}\n\nYth. Bapak/Ibu {nama_penerima},\n"
    "Perkara {nomor_spdp} telah memasuki hari ke-{hari_ke}.\n\n"
    "Nomor surat : {nomor_surat}\nTanggal surat: {tanggal_surat}\n"
    "Batas {masa_hari} hari: {tanggal_batas}\nStatus: {status_waktu}\n\n"
    "{tindak_lanjut}"
)


def update_default_templates(apps, schema_editor):
    NotificationTemplate = apps.get_model("notifications", "NotificationTemplate")
    updates = {
        "case_deadline_web": (
            OLD_WEB, NEW_WEB, "Reminder Tenggat Perkara - Aplikasi Web",
            "Reminder otomatis tiga hari terakhir pada setiap tahapan perkara.",
        ),
        "case_deadline_whatsapp": (
            OLD_CHANNEL, NEW_CHANNEL, "Reminder Tenggat Perkara - WhatsApp",
            "Reminder otomatis tiga hari terakhir melalui WhatsApp.",
        ),
        "case_deadline_telegram": (
            OLD_CHANNEL, NEW_CHANNEL, "Reminder Tenggat Perkara - Telegram",
            "Reminder otomatis tiga hari terakhir melalui Telegram.",
        ),
    }
    for key, (old_body, new_body, name, description) in updates.items():
        queryset = NotificationTemplate.objects.filter(key=key)
        queryset.filter(body_template=old_body).update(body_template=new_body)
        queryset.update(name=name, description=description)


class Migration(migrations.Migration):
    dependencies = [("notifications", "0009_case_deadline_reminders")]
    operations = [migrations.RunPython(update_default_templates, migrations.RunPython.noop)]
