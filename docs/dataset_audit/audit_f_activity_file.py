# -*- coding: utf-8 -*-
"""TAHAP 4 - Audit aktivitas, objek, path, hash (READ-ONLY).

Menghasilkan: 48, 49, 50, 51, 52, 53, 58, t4_stats.json. Tidak membuat hash
baru; hanya membaca dataset synthetic dan tabel PostgreSQL (SELECT-only).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
OUT = Path(__file__).resolve().parent


def pct(n, d):
    return round(100.0 * n / d, 4) if d else 0.0


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"[OK] {name} ({len(rows)} baris)")


synth = pd.read_csv(SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv",
                    encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])
N = len(synth)

# ------------------------------------------------ 48 skema kolom kedua dataset
SEMANTIC_SYNTH = {
    "timestamp": ("waktu event", "tanpa timezone"),
    "session_id": ("sesi aktivitas", "prefix S + hex"),
    "user_id": ("user", "ID dari tabel users dev"),
    "username": ("user", "nama akun"),
    "role": ("role", "Admin/Arsiparis/User"),
    "activity": ("aktivitas", "kosakata gaya UI Indonesia"),
    "status": ("status", "Berhasil/Gagal"),
    "ip_address": ("jaringan", "192.168.x.x saja"),
    "device": ("perangkat", "5 normal + 4 anomali"),
    "duration_ms": ("durasi", "ms; 0 utk sebagian besar anomali"),
    "object_count": ("jumlah objek", "angka; bukan identitas objek"),
    "risk_level": ("label ground-truth", "Normal/Low/Medium/High/Critical"),
    "anomaly_type": ("label ground-truth", "8 nilai"),
}
rows48 = []
for col in synth.columns:
    s = synth[col]
    rows48.append(["synthetic_raw", col, "string", N, int(s.isna().sum()),
                   int(s.nunique()), str(s.dropna().iloc[0]),
                   SEMANTIC_SYNTH.get(col, ("?", ""))[0],
                   SEMANTIC_SYNTH.get(col, ("", "-"))[1]])
for col in ["file/path/filename", "hash/checksum", "previous_hash",
            "document/case id", "target/resource"]:
    rows48.append(["synthetic_raw", col, "-", N, N, 0,
                   "(kolom tidak ada)", "-", "NOT_FOUND_IN_SYNTHETIC_DATASET"])

REAL_COLS = [
    ("id", "bigint", "PK"), ("user_id", "integer", "FK users"),
    ("aksi", "varchar(80)", "aktivitas UPPER_SNAKE_CASE"),
    ("target_tipe", "varchar(80)", "tipe objek: BERKAS/USER/PEMINJAMAN/dll"),
    ("target_id", "integer", "ID objek yang diaksi"),
    ("waktu", "timestamp", "waktu lokal server"),
    ("durasi_ms", "integer", "default 0"),
    ("jumlah_objek", "integer", "default 1"),
    ("status", "varchar(20)", "SUCCESS/VALID/dll"),
    ("ip_address", "varchar(45)", "'unknown' 333/337"),
    ("device", "varchar(255)", "'unknown' 333/337"),
    ("hash_sebelumnya", "char(64)", "hash entri terakhir sebelumnya"),
    ("hash_entri", "char(64)", "SHA-256 rantai entri"),
    ("file/path/nama_file", "-", "tidak ada kolom path/file di audit_log"),
    ("file_hash_sha256", "-", "hash FILE disimpan di tabel berkas.hash_sha256, BUKAN audit_log"),
]
try:
    import psycopg2

    conn = psycopg2.connect(host="localhost", port=5432, dbname="sistem_arsip_digital",
                            user="postgres", password="qethipen29", connect_timeout=5)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM audit_log")
    NR = int(cur.fetchone()[0])
    for col, dt, note in REAL_COLS[:13]:
        q = f'SELECT COUNT("{col}"), COUNT(DISTINCT "{col}") FROM audit_log'
        if col in ("hash_sebelumnya",):  # NULL pertama rantai dihitung missing
            q = 'SELECT COUNT(hash_sebelumnya), COUNT(DISTINCT hash_sebelumnya) FROM audit_log'
        cur.execute(q)
        total_c, uniq_c = cur.fetchone()
        cur.execute(f'SELECT "{col}" FROM audit_log ORDER BY id LIMIT 1')
        ex = cur.fetchone()[0]
        rows48.append(["postgresql_audit_log", col, dt, NR,
                       NR - int(total_c), int(uniq_c), str(ex)[:40], "?", note])
    for col, dt, note in REAL_COLS[13:]:
        rows48.append(["postgresql_audit_log", col, dt, NR, NR, 0,
                       "(kolom tidak ada)", "?", note])
    conn.rollback()

    # ------------------------------------------------ 49 distribusi aktivitas
    cur.execute("SELECT aksi, COUNT(*) FROM audit_log GROUP BY aksi ORDER BY COUNT(*) DESC")
    real_act = {a: int(c) for a, c in cur.fetchall()}
    conn.rollback()
    conn.close()
except Exception as exc:  # noqa: BLE001
    print("[DB] gagal:", repr(exc))
    NR, real_act = 0, {}

write_csv("48_activity_file_schema_audit.csv",
          ["dataset", "column_name", "data_type", "record_count", "missing_count",
           "unique_count", "example_value", "semantic_role", "notes"], rows48)

synth_act = synth["activity"].value_counts()
rows49 = [["synthetic_raw", a, int(c), pct(int(c), N)] for a, c in synth_act.items()]
rows49 += [["postgresql_audit_log", a, c, pct(c, NR)] for a, c in real_act.items()]
write_csv("49_activity_distribution_detailed.csv",
          ["dataset", "activity", "count", "percentage"], rows49)

# ------------------------------------------------ 50 perbandingan kosakata
SRC_EV = {
    "Login": "authController.js LOGIN_SUCCESS (login)",
    "Logout": "authController.js LOGOUT",
    "Lihat Berkas": "ACCESS_BERKAS_FILE (berkasController getBerkasFile)",
    "Cari Berkas": "ACCESS_BERKAS_FILE (pencarian tidak dilogging tersendiri)",
    "Input Berkas": "CREATE_BERKAS / UPDATE_BERKAS",
    "Verifikasi": "VERIFIKASI_INTEGRITAS_BERKAS / EXPORT_VERIFICATION_REPORT",
    "Dashboard": "NOT_FOUND - tidak ada createAuditLog",
    "Kelola User": "CREATE/UPDATE/DELETE_USER (userController)",
    "Lihat Perkara": "NOT_FOUND - perkaraController tidak memanggil createAuditLog untuk read",
    "Kelola Kode Klasifikasi": "NOT_FOUND",
}
all_act = sorted(set(synth_act.index) | set(real_act))
rows50 = []
for a in all_act:
    sc, rc = int(synth_act.get(a, 0)), int(real_act.get(a, 0))
    ev = SRC_EV.get(a)
    if ev is None:  # aksi real tanpa padanan synthetic -> cari evidence generik
        ev = "backend/controllers (grep createAuditLog) - tanpa padanan synthetic"
    notes = ""
    if sc and rc:
        notes = "padanan semantik; kosakata beda (Indonesia vs UPPER_SNAKE)"
    elif sc and not rc:
        notes = "hanya synthetic; tidak pernah terekam sistem nyata"
    else:
        notes = "hanya real; tidak direpresentasikan generator"
    rows50.append([a, sc, rc, int(sc > 0), int(rc > 0), ev, notes])
write_csv("50_activity_vocabulary_comparison.csv",
          ["activity", "synthetic_count", "real_count", "exists_in_synthetic",
           "exists_in_real", "source_code_evidence", "notes"], rows50)

# ------------------------------------------------ 51 relasi aktivitas-objek
rows51 = []
for a in synth_act.index:
    sub = synth[synth["activity"] == a]
    rows51.append([a, "object_count (angka agregat)", len(sub), "NO", "NO", "NO",
                   "identitas objek/file/path tidak ada; object_count hanya angka"])
for a in real_act:
    cur_rows = []
    conn = psycopg2.connect(host="localhost", port=5432, dbname="sistem_arsip_digital",
                            user="postgres", password="qethipen29", connect_timeout=5)
    cur = conn.cursor()
    cur.execute("SELECT target_tipe, target_id FROM audit_log WHERE aksi=%s", (a,))
    cur_rows = cur.fetchall()
    conn.rollback()
    conn.close()
    tt = {r[0] for r in cur_rows}
    has_doc = "YES" if any(r[1] is not None for r in cur_rows) else "NO"
    has_file = "YES" if "BERKAS" in tt else "NO"
    rows51.append([a, "target_tipe/target_id" if tt else "(null)", real_act[a],
                   has_file, "NO", has_doc,
                   f"target_tipe={sorted(tt) if tt else '-'}; audit_log tidak menyimpan path/hash file"])
write_csv("51_activity_object_relationship.csv",
          ["activity", "object_field", "record_count", "has_file", "has_path",
           "has_document_id", "notes"], rows51)

# ------------------------------------------------ 52/53 path & same-path
rows52 = [["(PATH_FIELD_NOT_AVAILABLE)",
           0, 0, "NOT_FOUND", "NOT_FOUND", "NOT_FOUND",
           "Tidak ada kolom path/filename pada dataset synthetic maupun tabel audit_log; path_file hanya ada di tabel berkas (database/schema.sql:111)"]]
write_csv("52_path_usage_audit.csv",
          ["path", "event_count", "unique_users", "activities", "first_timestamp",
           "last_timestamp"], rows52)

rows53 = [["HASH_NOT_AVAILABLE_IN_SYNTHETIC_DATASET", 0, 0, 0, "NOT_FOUND",
           "NOT_FOUND", "NOT_FOUND", "NOT_APPLICABLE",
           "Dataset synthetic tidak memiliki kolom path maupun hash; analisis same-path "
           "change dilakukan pada level aplikasi (lihat 56_same_path_hash_detection_analysis.md)"]]
write_csv("53_same_path_change_audit.csv",
          ["path", "event_count", "unique_hash_count", "unique_file_size_count",
           "first_timestamp", "last_timestamp", "activities", "change_detected",
           "evidence"], rows53)

# ------------------------------------------------ 58 profil integritas real
conn = psycopg2.connect(host="localhost", port=5432, dbname="sistem_arsip_digital",
                        user="postgres", password="qethipen29", connect_timeout=5)
cur = conn.cursor()
cur.execute("""
SELECT
  COUNT(*) AS total,
  COUNT(DISTINCT aksi) AS uniq_aksi,
  COUNT(target_tipe) AS with_target_tipe,
  COUNT(DISTINCT target_tipe) AS uniq_target_tipe,
  COUNT(target_id) AS with_target_id,
  COUNT(DISTINCT target_id) AS uniq_target_id,
  COUNT(hash_entri) AS with_hash_entri,
  COUNT(hash_sebelumnya) AS with_hash_sebelumnya,
  SUM(CASE WHEN status IN ('SUCCESS','VALID') THEN 1 ELSE 0 END) AS status_ok,
  MIN(waktu) AS tmin, MAX(waktu) AS tmax,
  COUNT(*) FILTER (WHERE ip_address='unknown') AS ip_unknown,
  COUNT(*) FILTER (WHERE device='unknown') AS dev_unknown
FROM audit_log
""")
r = cur.fetchone()
conn.rollback(); conn.close()
profile58 = [
    ["total_record", r[0], "100%", "audit_log"],
    ["unique_activity(aksi)", r[1], "", "UPPER_SNAKE_CASE"],
    ["records_with_target_tipe", r[2], pct(r[2], r[0]), "objek logis (BERKAS dll)"],
    ["unique_target_tipe", r[3], "", "nilai distinct"],
    ["records_with_target_id", r[4], pct(r[4], r[0]), "dokumen ID logis"],
    ["unique_target_id", r[5], "", ""],
    ["records_with_hash_entri(current_hash)", r[6], pct(r[6], r[0]), "SHA-256 chain"],
    ["records_with_hash_sebelumnya(previous_hash)", r[7], pct(r[7], r[0]),
     "1 NULL = baris pertama rantai"],
    ["status SUCCESS/VALID", r[8], pct(r[8], r[0]), ""],
    ["rentang waktu", f"{r[9]} s/d {r[10]}", "", ""],
    ["ip_address='unknown'", r[11], pct(r[11], r[0]), "default middleware"],
    ["device='unknown'", r[12], pct(r[12], r[0]), "default middleware"],
    ["path/filename di audit_log", 0, "0%", "NOT_FOUND - tidak ada kolom"],
    ["file hash di audit_log", 0, "0%",
     "hash file ada di berkas.hash_sha256, tidak masuk audit_log"],
]
with (OUT / "58_real_audit_log_integrity_profile.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["attribute", "value", "percentage", "notes"]] + profile58)
print("[OK] 58_real_audit_log_integrity_profile.csv")

stats = {
    "n_synth": N, "n_real": NR,
    "synth_activities": int(synth["activity"].nunique()),
    "real_activities": len(real_act),
    "real_top_aksi": dict(list(real_act.items())[:10]),
    "synth_object_columns": [c for c in synth.columns if "object" in c],
    "path_columns_synth": [], "hash_columns_synth": [],
    "profile58": profile58,
}
(OUT / "t4_stats.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
print("[OK] t4_stats.json")
