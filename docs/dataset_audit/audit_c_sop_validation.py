# -*- coding: utf-8 -*-
"""TAHAP 2 - Validasi dataset terhadap SOP & kondisi operasional (READ-ONLY).

Menghasilkan: 19, 20, 21, 22, 24, 26, 27 (CSV) + db_tahap2.json.
Tidak mengubah dataset/generator/model. Query DB hanya SELECT + ROLLBACK.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
OUT = Path(__file__).resolve().parent
DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

SYNTH = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv"


def pct(n, d):
    return round(100.0 * n / d, 4) if d else 0.0


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"[OK] {name} ({len(rows)} baris)")


synth = pd.read_csv(SYNTH, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
synth["ts"] = pd.to_datetime(synth["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
n_syn = len(synth)

# ---- data real (SELECT-only)
real_rows = []
db_meta = {}
try:
    import psycopg2

    conn = psycopg2.connect(host="localhost", port=5432, dbname="sistem_arsip_digital",
                            user="postgres", password="qethipen29", connect_timeout=5)
    cur = conn.cursor()
    cur.execute(
        """SELECT a.user_id, COALESCE(r.nama_peran,'(tanpa role)'), a.aksi, a.status,
                  a.device, a.ip_address, a.durasi_ms, a.jumlah_objek, a.waktu
           FROM audit_log a
           LEFT JOIN users u ON u.id = a.user_id
           LEFT JOIN roles r ON r.id = u.role_id
           ORDER BY a.id"""
    )
    real_rows = cur.fetchall()
    cur.execute("SELECT DISTINCT aksi FROM audit_log")
    db_meta["aksi_list"] = sorted(r[0] for r in cur.fetchall())
    conn.rollback()
    conn.close()
except Exception as exc:  # noqa: BLE001
    db_meta["error"] = repr(exc)
print(f"[DB] real rows={len(real_rows)}")

real = pd.DataFrame(real_rows, columns=["user_id", "role", "aksi", "status",
                                        "device", "ip_address", "durasi_ms",
                                        "jumlah_objek", "waktu"])
real["waktu"] = pd.to_datetime(real["waktu"])
n_real = len(real)

# ------------------------------------------------- 19 aktivitas vs SOP
SOURCE_AKSI = {
    # dari panggilan createAuditLog() di backend/controllers/* (grep Tahap 2)
    "LOGIN_SUCCESS": "authController.js", "LOGOUT": "authController.js",
    "CREATE_USER": "userController.js", "UPDATE_USER": "userController.js",
    "DELETE_USER": "userController.js",
    "CREATE_PERKARA": "perkaraController.js", "UPDATE_PERKARA": "perkaraController.js",
    "DELETE_PERKARA": "perkaraController.js",
    "CREATE_BERKAS": "berkasController.js", "UPDATE_BERKAS": "berkasController.js",
    "DELETE_BERKAS": "berkasController.js", "ACCESS_BERKAS_FILE": "berkasController.js",
    "VERIFIKASI_INTEGRITAS_BERKAS": "berkasController.js",
    "EXPORT_VERIFICATION_REPORT": "berkasController.js",
    "RETENSI_INAKTIF": "berkasController.js", "PERUBAHAN_STATUS_ARSIP": "berkasController.js",
    "CREATE_LEMARI": "lemariController.js", "UPDATE_LEMARI": "lemariController.js",
    "DELETE_LEMARI": "lemariController.js",
    "CREATE_RAK": "rakController.js", "UPDATE_RAK": "rakController.js",
    "DELETE_RAK": "rakController.js",
    "AJUKAN_PEMINJAMAN": "peminjamanController.js", "SETUJUI_PEMINJAMAN": "peminjamanController.js",
    "TOLAK_PEMINJAMAN": "peminjamanController.js", "PINJAM": "peminjamanController.js",
    "PENGEMBALIAN": "peminjamanController.js", "UPDATE_PEMINJAMAN": "peminjamanController.js",
    "DELETE_PEMINJAMAN": "peminjamanController.js",
    "SETUP_2FA_GENERATE": "totpController.js", "AKTIVASI_OTP": "totpController.js",
    "DISABLE_2FA_EMAIL_CHANGED": "totpController.js",
    "REQUEST_RESET_PASSWORD": "userController.js", "RESET_PASSWORD": "userController.js",
    "KEPUTUSAN_ANOMALI_OVERRIDE": "auditLogController.js",
    "KEPUTUSAN_ANOMALI_DITERIMA": "auditLogController.js",
}
CANON_BRIDGE = {  # synthetic -> kelas kanonik (utils/preprocessing_contract.py)
    "Login": "Login", "Logout": "Logout", "Lihat Perkara": "Kelola Perkara",
    "Lihat Berkas": "Akses Berkas", "Cari Berkas": "Akses Berkas",
    "Input Berkas": "Kelola Berkas", "Verifikasi": "Verifikasi",
    "Dashboard": "Laporan & Anomali", "Kelola User": "Kelola User",
    "Kelola Kode Klasifikasi": "Laporan & Anomali",
}
REAL_FOR_SYNTH = {
    "Login": ["LOGIN_SUCCESS"], "Logout": ["LOGOUT"],
    "Lihat Perkara": [],  # tidak ada aksi baca perkara
    "Lihat Berkas": ["ACCESS_BERKAS_FILE"], "Cari Berkas": ["ACCESS_BERKAS_FILE"],
    "Input Berkas": ["CREATE_BERKAS", "UPDATE_BERKAS"],
    "Verifikasi": ["VERIFIKASI_INTEGRITAS_BERKAS", "EXPORT_VERIFICATION_REPORT"],
    "Dashboard": [], "Kelola User": ["CREATE_USER", "UPDATE_USER", "DELETE_USER"],
    "Kelola Kode Klasifikasi": [],
}
sop_rows = []
syn_acts = set(synth["activity"].unique())
real_acts = set(real["aksi"].unique()) if n_real else set()
for act in sorted(syn_acts):
    in_real = [a for a in REAL_FOR_SYNTH.get(act, []) if a in real_acts]
    src_ok = bool(in_real)
    sop_rows.append([
        act, "YA", "YA" if in_real else "TIDAK", "YA" if src_ok else "TIDAK",
        "dokumen SOP tidak ditemukan di repository", "NEEDS_VERIFICATION" if src_ok else "NOT_FOUND",
        f"padanan real: {', '.join(in_real) if in_real else 'tidak ditemukan'}",
    ])
for aksi in sorted(real_acts - set(SOURCE_AKSI)):
    sop_rows.append([aksi, "TIDAK", "YA", "perlu verifikasi",
                     "dokumen SOP tidak ditemukan di repository", "NEEDS_VERIFICATION", "aksi real tanpa padanan synthetic"])
for aksi in sorted(set(SOURCE_AKSI) - real_acts):
    sop_rows.append([aksi, "TIDAK" if aksi not in ("LOGIN_SUCCESS", "LOGOUT") else "setara Login/Logout",
                     "YA (kode ada; belum terekam)", "YA",
                     "dokumen SOP tidak ditemukan di repository", "PARTIALLY_SUPPORTED",
                     f"didefinisikan di {SOURCE_AKSI[aksi]} namun belum muncul di log live"])
write_csv("19_activity_sop_validation.csv",
          ["aktivitas", "ada_di_synthetic", "ada_di_real", "ada_di_source_code",
           "dasar_sop", "status", "notes"], sop_rows)

# ------------------------------------------------- 20 role x aktivitas
ra_rows = []
g = synth.groupby(["role", "activity"]).size()
for (role, act), c in g.items():
    ra_rows.append(["synthetic_raw", role, act, int(c),
                    pct(int(c), int((synth["role"] == role).sum())),
                    "sesuai generator/flows.py", ""])
if n_real:
    gr = real.groupby(["role", "aksi"]).size()
    for (role, aksi), c in gr.items():
        ra_rows.append(["postgresql_real", role, aksi, int(c), pct(int(c), int((real["role"] == role).sum())),
                        "hasil JOIN users->roles (read-only)", ""])
write_csv("20_role_activity_validation.csv",
          ["dataset", "role", "activity", "count", "percentage_within_role", "evidence", "notes"], ra_rows)

# ------------------------------------------------- 21 jam kerja
def hour_bucket(h):
    if h < 7:
        return "<07:00"
    if h < 8:
        return "07:00-07:59"
    if h < 16:
        return "08:00-15:59"
    if h < 17:
        return "16:00-16:59"
    return ">=17:00"


wh_rows = []
for label, series in (("synthetic_raw", synth["ts"].dt.hour), ("postgresql_real", real["waktu"].dt.hour if n_real else None)):
    if series is None:
        continue
    vc = series.map(hour_bucket).value_counts()
    for cat in ["<07:00", "07:00-07:59", "08:00-15:59", "16:00-16:59", ">=17:00"]:
        c = int(vc.get(cat, 0))
        wh_rows.append([label, cat, c, pct(c, len(series))])
write_csv("21_working_hour_comparison.csv",
          ["dataset", "time_category", "record_count", "percentage"], wh_rows)

# ------------------------------------------------- 22 hari dalam minggu
wd_rows = []
for label, series in (("synthetic_raw", synth["ts"].dt.dayofweek), ("postgresql_real", real["waktu"].dt.dayofweek if n_real else None)):
    if series is None:
        continue
    vc = series.value_counts()
    for dw in range(7):
        c = int(vc.get(dw, 0))
        wd_rows.append([label, DAY_NAMES[dw], "weekday" if dw < 5 else "weekend", c,
                        pct(c, len(series))])
write_csv("22_weekday_comparison.csv",
          ["dataset", "day_of_week", "kategori", "record_count", "percentage"], wd_rows)

# ------------------------------------------------- 24 tanggal merah (UNKNOWN)
write_csv("24_holiday_analysis.csv",
          ["date", "day", "holiday_name", "activity_count", "dataset", "status", "notes"],
          [["-", "-", "TIDAK DAPAT DITENTUKAN", "", "semua",
            "NEEDS_VERIFICATION",
            "tidak ada sumber kalender tanggal merah di repository; daftar tidak direkonstruksi agar tidak mengarang"]])

# ------------------------------------------------- 26 matriks waktu operasional
mx_rows = []


def add_matrix(label, ts_series):
    dow = ts_series.dt.dayofweek
    hr = ts_series.dt.hour
    office = (hr >= 8) & (hr <= 15)
    n = len(ts_series)
    for kat_dow, mask_dow in (("hari_kerja(Sen-Jum)", dow < 5), ("weekend(Sab-Min)", dow >= 5)):
        for kat_jam, mask_jam in (("08:00-15:59", office), ("di_luar_08:00-15:59", ~office)):
            c = int((mask_dow & mask_jam).sum())
            mx_rows.append([label, kat_dow, kat_jam, c, pct(c, n)])
    mx_rows.append([label, "hari_libur", "(status UNKNOWN utk seluruh baris)", n,
                    100.0])


add_matrix("synthetic_raw", synth["ts"])
if n_real:
    add_matrix("postgresql_real", real["waktu"])
write_csv("26_operational_time_matrix.csv",
          ["dataset", "kategori_hari", "kategori_jam", "record_count", "percentage"], mx_rows)

# ------------------------------------------------- 27 perbandingan synthetic vs real
cmp_rows = []


def add(aspek, s_val, r_val, catatan=""):
    cmp_rows.append([aspek, str(s_val), str(r_val), catatan])


top_s = ", ".join(f"{k} ({v})" for k, v in synth["activity"].value_counts().head(5).items())
top_r = ""
if n_real:
    top_r = ", ".join(f"{k} ({v})" for k, v in real["aksi"].value_counts().head(5).items())
add("jumlah_record", n_syn, n_real)
add("rentang_waktu",
    f"{synth['ts'].min()} s/d {synth['ts'].max()}",
    f"{real['waktu'].min()} s/d {real['waktu'].max()}" if n_real else "-")
add("jenis_aktivitas_unik", synth["activity"].nunique(), real["aksi"].nunique() if n_real else 0,
    "kosakata berbeda (Indonesia vs UPPER_SNAKE_CASE)")
add("daftar_role", ", ".join(sorted(synth["role"].unique())),
    ", ".join(sorted(real["role"].unique())) if n_real else "-")
add("jumlah_user_unik", synth["user_id"].nunique(), real["user_id"].nunique() if n_real else 0)
add("aktivitas_teratas", top_s, top_r or "-")
dev_s = synth["device"].value_counts().to_dict()
dev_r = real["device"].value_counts().head(6).to_dict() if n_real else {}
add("distribusi_device", json.dumps(dev_s, ensure_ascii=False)[:300],
    json.dumps(dev_r, ensure_ascii=False)[:300], "real didominasi 'unknown'")
ip_s = {"private-192.168": int(synth["ip_address"].str.startswith("192.168.").sum()),
        "public-prefix-generator": int(synth["ip_address"].str.match(r"^(8\.|20\.|36\.|45\.|66\.|103\.|114\.|139\.|157\.|180\.)").sum())}
ip_r = real["ip_address"].value_counts().head(4).to_dict() if n_real else {}
add("distribusi_ip", json.dumps(ip_s), json.dumps(ip_r, ensure_ascii=False), "real didominasi 'unknown'")
add("atribut_hash_path_file", "TIDAK ADA pada kolom dataset",
    "ADA di tabel audit_log (hash_sebelumnya, hash_entri); TIDAK diekspor ke dataset",
    "rantai SHA-256 hanya level database")
add("jam_08:00-15:59", f"{pct(int(((synth['ts'].dt.hour>=8)&(synth['ts'].dt.hour<=15)).sum()), n_syn)}%",
    f"{pct(int(((real['waktu'].dt.hour>=8)&(real['waktu'].dt.hour<=15)).sum()), n_real)}%" if n_real else "-")
add("weekend_share", f"{pct(int((synth['ts'].dt.dayofweek>=5).sum()), n_syn)}%",
    f"{pct(int((real['waktu'].dt.dayofweek>=5).sum()), n_real)}%" if n_real else "-")
add("status_vocabulary", ", ".join(sorted(synth["status"].unique())),
    ", ".join(sorted(real["status"].unique())) if n_real else "-")
add("durasi_ms_min_max",
    f"{pd.to_numeric(synth['duration_ms']).min()} - {pd.to_numeric(synth['duration_ms']).max()}",
    f"{real['durasi_ms'].min()} - {real['durasi_ms'].max()}" if n_real else "-")
add("object_count_min_max",
    f"{pd.to_numeric(synth['object_count']).min()} - {pd.to_numeric(synth['object_count']).max()}",
    f"{real['jumlah_objek'].min()} - {real['jumlah_objek'].max()}" if n_real else "-")
write_csv("27_synthetic_real_comparison.csv",
          ["aspek", "nilai_synthetic", "nilai_real", "catatan"], cmp_rows)

(OUT / "db_tahap2.json").write_text(json.dumps(db_meta, indent=2), encoding="utf-8")
print("[OK] db_tahap2.json")
