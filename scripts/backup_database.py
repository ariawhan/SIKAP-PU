"""Membuat backup sebelum migrasi. Kegagalan backup menghentikan update."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
host, user = os.getenv("DB_HOST", "127.0.0.1"), os.getenv("DB_USER", "root")
port, password = int(os.getenv("DB_PORT", "3306")), os.getenv("DB_PASSWORD", "")
database = os.getenv("DB_NAME", "sikap_pu_db")
with pymysql.connect(host=host, port=port, user=user, password=password, database=database) as connection:
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        if not cursor.fetchone():
            print("[INFO] Database masih kosong; backup belum diperlukan.")
            raise SystemExit(0)

xampp = Path(os.getenv("XAMPP_PATH", r"C:\xampp"))
dump_tool = xampp / "mysql" / "bin" / "mysqldump.exe"
if not dump_tool.exists():
    raise SystemExit(f"mysqldump tidak ditemukan di {dump_tool}. Migrasi dibatalkan demi keamanan data.")
backup_dir = ROOT / "backups"
backup_dir.mkdir(exist_ok=True)
target = backup_dir / f"sikap_pu_{datetime.now():%Y%m%d_%H%M%S}.sql"
command = [str(dump_tool), f"--host={host}", f"--port={port}", f"--user={user}", "--single-transaction", "--routines", "--events", "--default-character-set=utf8mb4"]
if password:
    command.append(f"--password={password}")
command.append(database)
with target.open("wb") as output:
    result = subprocess.run(command, stdout=output, stderr=subprocess.PIPE, check=False)
if result.returncode:
    target.unlink(missing_ok=True)
    print(result.stderr.decode(errors="replace"), file=sys.stderr)
    raise SystemExit("Backup gagal. Migrasi dibatalkan agar data lama tetap aman.")
print(f"[OK] Backup tersimpan: {target}")

