"""Utility database PostgreSQL untuk AI Service."""

from typing import List

import pandas as pd
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from config import get_database_config


AUDIT_LOG_COLUMNS: List[str] = [
    "waktu",
    "user_id",
    "aksi",
    "target_tipe",
    "ip_address",
    "device",
    "status",
    "durasi_ms",
    "jumlah_objek",
]


def get_database_engine() -> Engine:
    """Membuat SQLAlchemy engine untuk koneksi PostgreSQL."""
    database_config = get_database_config()
    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username=str(database_config["user"]),
        password=str(database_config["password"]),
        host=str(database_config["host"]),
        port=int(database_config["port"]),
        database=str(database_config["database"]),
    )
    return create_engine(database_url, pool_pre_ping=True)


def fetch_audit_log_dataframe() -> pd.DataFrame:
    """Mengambil audit log dari PostgreSQL hanya untuk kolom fitur VAE.

    Raises:
        RuntimeError: Jika query audit_log gagal dijalankan.
    """
    quoted_columns = ", ".join(f'"{column}"' for column in AUDIT_LOG_COLUMNS)
    query = text(f"SELECT {quoted_columns} FROM audit_log")

    try:
        engine = get_database_engine()
        with engine.connect() as connection:
            return pd.read_sql_query(query, connection)
    except Exception as error:
        raise RuntimeError(f"Gagal mengambil data audit_log: {error}") from error


def test_database_connection() -> bool:
    """Memeriksa apakah database dapat diakses oleh AI Service."""
    try:
        engine = get_database_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
