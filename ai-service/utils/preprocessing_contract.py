"""Single Source of Truth Preprocessing Contract for VAE Anomaly Detection.

This module provides deterministic, canonical transformations for both training and inference.
Guarantees 100% contract synchronization and eliminates domain shift distortions.
"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Fixed, deterministic class vocabularies
ACTIVITY_CLASSES: List[str] = [
    "Login",
    "Logout",
    "Akses Berkas",
    "Kelola Berkas",
    "Kelola Perkara",
    "Kelola Sarana",
    "Kelola User",
    "Keamanan & 2FA",
    "Peminjaman",
    "Verifikasi",
    "Laporan & Anomali",
    "UNKNOWN",
]

STATUS_CLASSES: List[str] = [
    "Berhasil",
    "Gagal",
    "UNKNOWN",
]

DEVICE_CLASSES: List[str] = [
    "PC Windows",
    "Android",
    "iOS",
    "MacOS",
    "Linux",
    "Virtual Machine",
    "Unknown Device",
]

IP_CLASSES: List[str] = [
    "Localhost / Loopback",
    "Private Network 192.168.x.x",
    "Private Network 10.x.x.x",
    "Private Network 172.16-31.x.x",
    "Public IP Address",
    "UNKNOWN",
]

# Exact 9 feature ordering
FEATURE_COLUMNS: Tuple[str, ...] = (
    "user_id",
    "activity",
    "status",
    "device",
    "ip_address",
    "duration_ms",
    "object_count",
    "hour",
    "day_of_week",
)


def map_canonical_activity(activity_input: Any) -> str:
    """Map raw activity string to canonical activity category."""
    if not activity_input:
        return "UNKNOWN"

    act = str(activity_input).strip().upper()

    if act in ("LOGIN", "LOGIN_SUCCESS"):
        return "Login"
    if act in ("LOGOUT",):
        return "Logout"
    if act in ("ACCESS_BERKAS_FILE", "LIHAT_BERKAS", "CARI_BERKAS", "LIHAT BERKAS", "CARI BERKAS"):
        return "Akses Berkas"
    if act in ("CREATE_BERKAS", "UPDATE_BERKAS", "DELETE_BERKAS", "INPUT_BERKAS", "INPUT BERKAS"):
        return "Kelola Berkas"
    if act in ("CREATE_PERKARA", "UPDATE_PERKARA", "DELETE_PERKARA", "LIHAT_PERKARA", "LIHAT PERKARA"):
        return "Kelola Perkara"
    if act in (
        "CREATE_LEMARI", "UPDATE_LEMARI", "DELETE_LEMARI",
        "CREATE_RAK", "UPDATE_RAK", "DELETE_RAK"
    ):
        return "Kelola Sarana"
    if act in ("CREATE_USER", "UPDATE_USER", "DELETE_USER", "KELOLA_USER", "KELOLA USER"):
        return "Kelola User"
    if act in (
        "SETUP_2FA_GENERATE", "AKTIVASI_OTP", "DISABLE_2FA_EMAIL_CHANGED",
        "REQUEST_RESET_PASSWORD", "RESET_PASSWORD", "SETUP 2FA", "VERIFIKASI OTP"
    ):
        return "Keamanan & 2FA"
    if act in (
        "AJUKAN_PEMINJAMAN", "SETUJUI_PEMINJAMAN", "TOLAK_PEMINJAMAN",
        "PINJAM", "PENGEMBALIAN", "UPDATE_PEMINJAMAN", "DELETE_PEMINJAMAN", "PEMINJAMAN"
    ):
        return "Peminjaman"
    if act in ("VERIFIKASI_INTEGRITAS_BERKAS", "VERIFIKASI"):
        return "Verifikasi"
    if act in (
        "EXPORT_VERIFICATION_REPORT", "KEPUTUSAN_ANOMALI_OVERRIDE",
        "KEPUTUSAN_ANOMALI_DITERIMA", "DASHBOARD", "KELOLA_KLASIFIKASI",
        "KELOLA KODE KLASIFIKASI"
    ):
        return "Laporan & Anomali"

    raw_str = str(activity_input).strip()
    if raw_str in ACTIVITY_CLASSES:
        return raw_str

    return "UNKNOWN"


def map_canonical_status(status_input: Any) -> str:
    """Map raw status string to canonical status category."""
    if not status_input:
        return "UNKNOWN"

    stat = str(status_input).strip().upper()
    if stat in ("SUCCESS", "VALID", "BERHASIL", "OK"):
        return "Berhasil"
    if stat in ("FAILED", "GAGAL", "INVALID", "ERROR"):
        return "Gagal"

    raw_str = str(status_input).strip()
    if raw_str in STATUS_CLASSES:
        return raw_str

    return "UNKNOWN"


def parse_user_agent_device(device_input: Any) -> str:
    """Parse User-Agent string or device name into canonical device category."""
    if not device_input:
        return "Unknown Device"

    dev_str = str(device_input).strip()
    dev_upper = dev_str.upper()

    if re.search(r"WINDOWS|WIN64|WIN32", dev_upper):
        return "PC Windows"
    if re.search(r"ANDROID", dev_upper):
        return "Android"
    if re.search(r"IPHONE|IPAD|IOS", dev_upper):
        return "iOS"
    if re.search(r"MACINTOSH|MAC OS|MACOS", dev_upper):
        return "MacOS"
    if re.search(r"LINUX|X11", dev_upper):
        return "Linux"
    if re.search(r"VM|VIRTUAL", dev_upper):
        return "Virtual Machine"

    if dev_str in DEVICE_CLASSES:
        return dev_str

    return "Unknown Device"


def map_ip_category(ip_input: Any) -> str:
    """Map IP address string to safe categorical domain representation."""
    if not ip_input or pd.isna(ip_input):
        return "UNKNOWN"

    ip_str = str(ip_input).strip().lower()

    if ip_str in ("127.0.0.1", "::1", "localhost", "0.0.0.0", "unknown") or "127.0.0.1" in ip_str:
        return "Localhost / Loopback"

    if ip_str.startswith("::ffff:"):
        ip_str = ip_str.replace("::ffff:", "")
        if ip_str.startswith("127."):
            return "Localhost / Loopback"

    if ip_str.startswith("192.168."):
        return "Private Network 192.168.x.x"
    if ip_str.startswith("10."):
        return "Private Network 10.x.x.x"

    if ip_str.startswith("172."):
        try:
            second_octet = int(ip_str.split(".")[1])
            if 16 <= second_octet <= 31:
                return "Private Network 172.16-31.x.x"
        except (IndexError, ValueError):
            pass

    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_loopback:
            return "Localhost / Loopback"
        if ip_obj.is_private:
            return "Private Network 192.168.x.x"
        return "Public IP Address"
    except ValueError:
        return "UNKNOWN"


def parse_timestamp_wib(waktu_input: Any) -> Tuple[int, int]:
    """Parse ISO or datetime string and convert to Asia/Jakarta (WIB) hour and dayofweek."""
    try:
        dt = pd.to_datetime(waktu_input)
        if dt.tzinfo is not None:
            dt = dt.tz_convert("Asia/Jakarta")
        else:
            dt = dt.tz_localize("UTC").tz_convert("Asia/Jakarta")
        return int(dt.hour), int(dt.dayofweek)
    except Exception:
        now = datetime.now()
        return int(now.hour), int(now.weekday())


def transform_numeric_features(
    user_id: Any, durasi_ms: Any, jumlah_objek: Any
) -> Tuple[float, float, float]:
    """Safely transform numeric features with max(0) and log1p scaling."""
    try:
        uid = float(user_id)
        if not np.isfinite(uid):
            uid = 1.0
    except (ValueError, TypeError):
        uid = 1.0

    try:
        dur = float(durasi_ms)
        if not np.isfinite(dur) or dur < 0:
            dur = 0.0
    except (ValueError, TypeError):
        dur = 0.0

    try:
        obj = float(jumlah_objek)
        if not np.isfinite(obj) or obj < 0:
            obj = 0.0
    except (ValueError, TypeError):
        obj = 0.0

    return uid, float(np.log1p(dur)), float(np.log1p(obj))


def process_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract canonical representation of an audit_log record."""
    uid, dur_log1p, obj_log1p = transform_numeric_features(
        record.get("user_id", 1),
        record.get("durasi_ms", record.get("duration_ms", 0.0)),
        record.get("jumlah_objek", record.get("object_count", 0.0)),
    )
    hour_wib, day_of_week = parse_timestamp_wib(record.get("waktu", record.get("timestamp", "")))

    return {
        "user_id": uid,
        "activity": map_canonical_activity(record.get("aksi", record.get("activity", ""))),
        "status": map_canonical_status(record.get("status", "")),
        "device": parse_user_agent_device(record.get("device", "")),
        "ip_address": map_ip_category(record.get("ip_address", "")),
        "duration_ms": dur_log1p,
        "object_count": obj_log1p,
        "hour": hour_wib,
        "day_of_week": day_of_week,
    }
