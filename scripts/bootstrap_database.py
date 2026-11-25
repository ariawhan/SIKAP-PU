"""Membuat database jika belum ada tanpa menyentuh data yang sudah tersimpan."""
import os
import time
from pathlib import Path
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
host, user = os.getenv("DB_HOST", "127.0.0.1"), os.getenv("DB_USER", "root")
port, password = int(os.getenv("DB_PORT", "3306")), os.getenv("DB_PASSWORD", "")
database = os.getenv("DB_NAME", "sikap_pu_db")
legacy_databases = [
    name.strip()
    for name in os.getenv("LEGACY_DB_NAMES", "pidum_db").split(",")
    if name.strip() and name.strip() != database
]


def valid_database_name(name):
    return name.replace("_", "").isalnum()


if not valid_database_name(database) or any(not valid_database_name(name) for name in legacy_databases):
    raise SystemExit("Nama database hanya boleh berisi huruf, angka, dan garis bawah.")


def database_exists(cursor, name):
    cursor.execute(
        "SELECT 1 FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s",
        (name,),
    )
    return cursor.fetchone() is not None


def database_tables(cursor, name):
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME",
        (name,),
    )
    return [row[0] for row in cursor.fetchall()]


def copy_legacy_database(cursor, source, target):
    source_tables = database_tables(cursor, source)
    if not source_tables:
        return 0

    created_tables = []
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    try:
        for table in source_tables:
            cursor.execute(f"SHOW CREATE TABLE `{source}`.`{table}`")
            create_sql = cursor.fetchone()[1]
            create_sql = create_sql.replace(
                f"CREATE TABLE `{table}`",
                f"CREATE TABLE `{target}`.`{table}`",
                1,
            )
            cursor.execute(create_sql)
            created_tables.append(table)

        for table in source_tables:
            cursor.execute(f"INSERT INTO `{target}`.`{table}` SELECT * FROM `{source}`.`{table}`")
            cursor.execute(f"SELECT COUNT(*) FROM `{source}`.`{table}`")
            source_count = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM `{target}`.`{table}`")
            target_count = cursor.fetchone()[0]
            if source_count != target_count:
                raise RuntimeError(f"Verifikasi tabel {table} gagal ({source_count} != {target_count}).")
    except Exception:
        # Target dipastikan kosong sebelum proses ini. Database lama tidak pernah disentuh.
        for table in reversed(created_tables):
            cursor.execute(f"DROP TABLE IF EXISTS `{target}`.`{table}`")
        raise
    finally:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    return len(source_tables)

connection = None
last_error = None
for attempt in range(30):
    try:
        connection = pymysql.connect(host=host, port=port, user=user, password=password, charset="utf8mb4", connect_timeout=2)
        break
    except pymysql.MySQLError as exc:
        last_error = exc
        if attempt == 29:
            raise SystemExit(
                "MySQL belum dapat dihubungi. Periksa XAMPP dan konfigurasi .env.\n"
                f"Detail MariaDB: {last_error}"
            )
        time.sleep(1)
with connection:
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        target_tables = database_tables(cursor, database)
        if not target_tables:
            for legacy_database in legacy_databases:
                if not database_exists(cursor, legacy_database):
                    continue
                legacy_tables = database_tables(cursor, legacy_database)
                if not legacy_tables:
                    continue
                print(
                    f"[INFO] Database lama '{legacy_database}' ditemukan. "
                    f"Menyalin data ke '{database}' tanpa menghapus sumber..."
                )
                try:
                    copied = copy_legacy_database(cursor, legacy_database, database)
                except Exception as exc:
                    raise SystemExit(
                        "Pemindahan database lama gagal. Database sumber tetap aman dan tidak dihapus.\n"
                        f"Detail: {exc}"
                    ) from exc
                print(f"[OK] {copied} tabel berhasil disalin dan diverifikasi dari '{legacy_database}'.")
                break
print(f"[OK] Database '{database}' siap digunakan.")
