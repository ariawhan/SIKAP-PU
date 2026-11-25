@echo off
setlocal EnableExtensions
title SIKAP-PU - WA Gateway
cd /d "%~dp0Wa-Gateway"

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js belum terpasang atau belum masuk PATH.
  echo Unduh Node.js LTS dari https://nodejs.org/
  pause
  exit /b 1
)

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo [INFO] File Wa-Gateway\.env dibuat dari contoh.
)

if not exist "node_modules" (
  echo [INFO] Memasang dependensi Wa-Gateway...
  npm install
  if errorlevel 1 goto failed
)

echo [OK] Menjalankan Wa-Gateway di http://127.0.0.1:3001
npm start
exit /b %errorlevel%

:failed
echo.
echo [ERROR] Wa-Gateway gagal disiapkan.
pause
exit /b 1
