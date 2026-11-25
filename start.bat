@echo off
setlocal EnableExtensions
title SIKAP-PU - Menyiapkan Aplikasi
cd /d "%~dp0"
echo.
echo  =============================================
echo     SIKAP-PU - Kejaksaan Republik Indonesia
echo  =============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python belum terpasang atau belum masuk PATH.
  echo Unduh Python dari https://www.python.org/downloads/
  echo Saat instalasi, centang pilihan "Add Python to PATH".
  pause
  exit /b 1
)

if defined XAMPP_PATH goto xampp_found
if exist "C:\xampp\mysql\bin\mysqld.exe" set "XAMPP_PATH=C:\xampp"
if not defined XAMPP_PATH if exist "D:\xampp\mysql\bin\mysqld.exe" set "XAMPP_PATH=D:\xampp"
if not defined XAMPP_PATH if exist "E:\xampp\mysql\bin\mysqld.exe" set "XAMPP_PATH=E:\xampp"
:xampp_found
if not defined XAMPP_PATH (
  echo [ERROR] XAMPP tidak ditemukan di C:\xampp, D:\xampp, atau E:\xampp.
  echo Atur variabel XAMPP_PATH ke folder instalasi XAMPP.
  pause
  exit /b 1
)

tasklist /FI "IMAGENAME eq mysqld.exe" 2>nul | find /I "mysqld.exe" >nul
if errorlevel 1 (
  echo [INFO] Menyalakan MySQL XAMPP...
  start "SIKAP-PU MySQL" /min cmd /c ""%XAMPP_PATH%\mysql_start.bat""
) else (
  echo [OK] MySQL sudah berjalan.
)

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo [INFO] File .env dibuat dari konfigurasi bawaan.
)
if not exist ".venv\Scripts\python.exe" (
  echo [INFO] Membuat virtual environment...
  py -m venv .venv
  if errorlevel 1 goto failed
)

set "PYTHON=.venv\Scripts\python.exe"
echo [INFO] Memastikan dependensi terpasang...
"%PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
echo [INFO] Menyiapkan database...
"%PYTHON%" scripts\bootstrap_database.py
if errorlevel 1 goto failed
echo [INFO] Membuat backup sebelum pembaruan struktur...
"%PYTHON%" scripts\backup_database.py
if errorlevel 1 goto failed
echo [INFO] Menjalankan migrasi Django tanpa menghapus data...
"%PYTHON%" manage.py migrate --noinput
if errorlevel 1 goto failed
echo [INFO] Memastikan akun Super Admin awal tersedia...
"%PYTHON%" manage.py ensure_initial_admin
if errorlevel 1 goto failed
echo [INFO] Memeriksa konfigurasi aplikasi...
"%PYTHON%" manage.py check
if errorlevel 1 goto failed
echo [INFO] Auto-reload server dan browser aktif selama mode pengembangan.
where node >nul 2>nul
if errorlevel 1 (
  echo [INFO] Node.js tidak ditemukan. Wa-Gateway tidak dinyalakan otomatis.
) else (
  echo [INFO] Menyalakan Wa-Gateway WhatsApp...
  start "SIKAP-PU WA Gateway" cmd /c "start-wa-gateway.bat"
)
echo [INFO] Menyalakan worker notifikasi di background...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start_background_workers.ps1" -PythonPath "%PYTHON%" -ProjectRoot "%CD%"
if errorlevel 1 (
  echo [ERROR] Worker notifikasi gagal dijalankan.
  echo Periksa folder logs\workers untuk detail error.
  goto failed
)
set "WIFI_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\get_wifi_ip.ps1"`) do set "WIFI_IP=%%I"
echo.
echo [OK] SIKAP-PU berjalan di komputer ini: http://127.0.0.1:8000
if defined WIFI_IP echo [OK] Akses dari perangkat satu Wi-Fi: http://%WIFI_IP%:8000
echo [OK] Wa-Gateway lokal: http://127.0.0.1:3001
if not defined WIFI_IP echo [INFO] IP jaringan tidak ditemukan. Pastikan Wi-Fi aktif.
echo Tekan Ctrl+C pada jendela ini untuk menghentikan aplikasi.
echo.
"%PYTHON%" manage.py runserver 0.0.0.0:8000
exit /b %errorlevel%

:failed
echo.
echo [ERROR] Proses startup dihentikan. Data lama tidak dihapus.
pause
exit /b 1
