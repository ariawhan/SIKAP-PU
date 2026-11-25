# SIKAP-PU — Django + Tailwind CSS

**SIKAP-PU** (Sistem Informasi Kendali Administrasi Perkara Tindak Pidana Umum pada Tahap Pra Penuntutan Berbasis Web dengan Automatic Reminder WhatsApp dan Telegram) — fondasi digitalisasi administrasi Pidana Umum menggunakan Django 5.2 LTS, Tailwind CSS, CSS khusus SIKAP-PU, dan MySQL/MariaDB dari XAMPP.

Proyek menyertakan backend kompatibilitas untuk MariaDB 10.4 pada XAMPP lama. Untuk server produksi tetap disarankan memakai MariaDB 10.5 atau lebih baru yang didukung resmi oleh Django 5.2.

## Fitur awal

- Login dengan username atau email
- Dashboard modern dan responsif
- Role `Admin` dan `Super Admin`
- Manajemen pengguna khusus Super Admin
- Password hashing, CSRF protection, session authentication, dan validasi password Django
- Django Admin di `/django-admin/`

## Menjalankan otomatis (direkomendasikan)

Pastikan Python, XAMPP, dan Node.js LTS sudah terpasang, kemudian klik dua kali **`start.bat`**. Script tersebut otomatis:

- mencari dan menyalakan MySQL XAMPP;
- membuat `.env` dan virtual environment jika belum tersedia;
- memasang atau memperbarui dependensi;
- membuat database `sikap_pu_db` jika belum ada;
- menyalin dan memverifikasi data dari database lama `pidum_db` apabila `sikap_pu_db` masih kosong, tanpa menghapus database asal;
- membuat backup database sebelum perubahan struktur;
- menjalankan migrasi Django tanpa menghapus data;
- membuat Super Admin pertama jika belum ada pengguna;
- menyalakan **Wa-Gateway** di jendela terpisah jika Node.js tersedia; dan
- menjalankan aplikasi di `http://127.0.0.1:8000`.

Password Super Admin acak hanya ditampilkan pada startup pertama. Alternatifnya, isi `INITIAL_ADMIN_PASSWORD` di `.env` sebelum startup pertama.

## Wa-Gateway WhatsApp

Folder **`Wa-Gateway`** adalah server Node.js pendamping untuk WhatsApp berbasis library `wa-multi-session`. SIKAP-PU tetap berjalan di port `8000`, sedangkan gateway WhatsApp berjalan lokal di `http://127.0.0.1:3001`.

Jalankan manual jika diperlukan:

```bat
start-wa-gateway.bat
```

Halaman **Notifikasi** menampilkan log pengiriman, status session, dan barcode scan. Menu **Setting Template Notifikasi** khusus Super Admin digunakan untuk mengubah pesan otomatis WhatsApp, Telegram, serta notifikasi web tanpa mengubah kode. Konfigurasi koneksi ada di `.env`:

```env
WA_GATEWAY_URL=http://127.0.0.1:3001
WA_GATEWAY_API_KEY=ganti-dengan-secret-yang-panjang
WA_GATEWAY_SESSION=sikap-pu-main
```

## Instalasi manual dengan XAMPP

1. Instal Python 3.11 atau lebih baru, lalu aktifkan MySQL melalui XAMPP.
2. Buat database melalui phpMyAdmin:

   ```sql
   CREATE DATABASE sikap_pu_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. Siapkan dan jalankan aplikasi:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   py manage.py migrate
   py manage.py createsuperuser
   py manage.py runserver
   ```

4. Buka `http://127.0.0.1:8000`.

Selama `DJANGO_DEBUG=True`, `runserver` akan restart otomatis ketika kode Python berubah. Browser juga akan memuat ulang otomatis ketika file Python, template, CSS, atau JavaScript disimpan. Untuk mematikannya, isi `DJANGO_BROWSER_AUTO_RELOAD=False` pada `.env`.

Akun dari `createsuperuser` otomatis memiliki akses Super Admin. Pengguna tambahan dapat dibuat dari menu **Pengguna** di dashboard.

## Mengisi data perkara untuk pengembangan

Untuk meninjau tampilan daftar, dashboard, dan alur dokumen, jalankan:

```powershell
py manage.py populate_case_data
```

Perintah ini menambahkan 50 perkara contoh dengan variasi subjek hukum, status, pelaku, korban, tanda terima, penunjukan jaksa, Tahap 1, dan dokumen lanjutan. Isinya fiktif, tidak memakai nomor identitas pribadi, dan disajikan seperti catatan perkara biasa. Perintah aman dijalankan ulang: perkara yang sudah ada tidak digandakan. Konfigurasi unit penyidik aktif diperlukan; akun aktif ber-role Kasi Pidum dan Jaksa diperlukan untuk mengisi alur penunjukan.

## Pembaruan tanpa kehilangan data

Jalankan kembali `start.bat` setelah source code diperbarui. Django hanya menerapkan migrasi yang belum pernah dijalankan. Script tidak menjalankan `flush`, `DROP DATABASE`, atau menghapus tabel. Sebelum migrasi, salinan SQL disimpan di folder `backups/`. Jika backup gagal, proses migrasi dibatalkan.

## Pengujian

```powershell
py manage.py test
```

Tailwind Play CDN dipakai agar prototype langsung berjalan tanpa Node.js. Untuk produksi, ganti CDN dengan hasil build Tailwind CLI dan jalankan `py manage.py collectstatic`.
