# -*- coding: utf-8 -*-
"""TAHAP 1 - Audit forensik bagian B (READ-ONLY).

Menghasilkan: 06_timestamp_hour_analysis.csv, 07_calendar_analysis.csv,
08_activity_distribution.csv, 09_actor_distribution.csv, 10_network_distribution.csv,
11_file_integrity_audit.csv, 12_stage5_claim_verification.csv, db_check.json.

Query database hanya SELECT dan selalu diakhiri ROLLBACK. Tidak mengubah apa pun.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
OUT = Path(__file__).resolve().parent
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DATASETS = {
    "synthetic_raw": SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv",
    "retraining_combined_raw": SVC / "dataset" / "retraining" / "retraining_dataset_combined_raw.csv",
    "retraining_canonical": SVC / "dataset" / "retraining" / "retraining_dataset_canonical.csv",
}


def load_csv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])


def pct(n, d):
    return round(100.0 * n / d, 4) if d else 0.0


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"[OK] {name} ({len(rows)} baris)")


frames = {k: load_csv(p) for k, p in DATASETS.items()}
main = frames["synthetic_raw"]
combined = frames["retraining_combined_raw"]
canonical = frames["retraining_canonical"]
n_main = len(main)

# ------------------------------------------------------- 06 timestamp per jam
hour_rows = []
bucket_rows = []
range_rows = []
ts_cache = {}
for key in ["synthetic_raw", "retraining_combined_raw"]:
    df = frames[key]
    if df is None or "timestamp" not in df.columns:
        continue
    t = pd.to_datetime(df["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    ts_cache[key] = t
    valid = t.dropna()
    range_rows.append([key, str(valid.min()), str(valid.max()), int(t.isna().sum())])
    by_hour = t.dt.hour.value_counts()
    for h in range(24):
        hour_rows.append([key, h, f"{h:02d}:00-{h:02d}:59", int(by_hour.get(h, 0)),
                          pct(int(by_hour.get(h, 0)), len(df))])
    b_before = int((t.dt.hour < 8).sum())
    b_office = int(((t.dt.hour >= 8) & (t.dt.hour <= 15)).sum())
    b_after = int((t.dt.hour >= 16).sum())
    bucket_rows.append([key, "<08:00", b_before, pct(b_before, len(df))])
    bucket_rows.append([key, "08:00-15:59", b_office, pct(b_office, len(df))])
    bucket_rows.append([key, ">=16:00", b_after, pct(b_after, len(df))])

# agregasi per tanggal + hari (untuk 06 juga)
date_rows = []
for key, t in ts_cache.items():
    counts = t.dt.date.value_counts().sort_index()
    for d, c in counts.items():
        date_rows.append([key, str(d), DAY_NAMES[pd.Timestamp(d).dayofweek], int(c)])
write_csv("06_timestamp_hour_analysis.csv", ["dataset", "date", "day_of_week", "activity_count"], date_rows)
with (OUT / "06a_per_jam.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["dataset", "hour", "jam_label", "count", "percentage"])
    w.writerows(hour_rows + [[""]])
    for r in bucket_rows:
        w.writerow([r[0], f"BUKET {r[1]}", r[1], r[2], r[3]])
print("[OK] 06a_per_jam.csv")
with (OUT / "06b_rentang.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["dataset", "timestamp_min", "timestamp_max", "unparseable"])
    w.writerows(range_rows)
print("[OK] 06b_rentang.csv")

# ------------------------------------------------------------- 07 kalender F
cal_rows = []
for key, t in ts_cache.items():
    counts = t.dt.date.value_counts().sort_index()
    for d, c in counts.items():
        dow = pd.Timestamp(d).dayofweek
        cal_rows.append([key, str(d), DAY_NAMES[dow],
                         "weekday" if dow < 5 else "weekend", "UNKNOWN", int(c),
                         "sumber daftar tanggal merah tidak ditemukan di repository"])
write_csv("07_calendar_analysis.csv",
          ["dataset", "date", "day_of_week", "weekday_weekend", "holiday_status", "activity_count", "notes"], cal_rows)

# ---------------------------------------------------------- 08 aktivitas G/H
act_rows = []
for key in ["synthetic_raw", "retraining_combined_raw"]:
    df = frames[key]
    if df is None:
        continue
    col = "activity" if "activity" in df.columns else ("aksi" if "aksi" in df.columns else None)
    if col:
        vc = df[col].value_counts()
        for val, c in vc.items():
            act_rows.append([key, "activity", str(val), int(c), pct(int(c), len(df))])
    if "status" in df.columns:
        for val, c in df["status"].value_counts().items():
            act_rows.append([key, "status", str(val), int(c), pct(int(c), len(df))])
    if "anomaly_type" in df.columns:
        for val, c in df["anomaly_type"].value_counts().items():
            act_rows.append([key, "anomaly_type(label)", str(val), int(c), pct(int(c), len(df))])
    if "risk_level" in df.columns:
        for val, c in df["risk_level"].value_counts().items():
            act_rows.append([key, "risk_level(label)", str(val), int(c), pct(int(c), len(df))])
if canonical is not None:
    col = "activity" if "activity" in canonical.columns else ("aksi" if "aksi" in canonical.columns else None)
    if col:
        for val, c in canonical[col].value_counts().items():
            act_rows.append(["retraining_canonical", "activity(canonical)", str(val), int(c),
                             pct(int(c), len(canonical))])
write_csv("08_activity_distribution.csv", ["dataset", "column", "value", "count", "percentage"], act_rows)

# ------------------------------------------------------------- 09 aktor G/H
actor_rows = []
for key in ["synthetic_raw", "retraining_combined_raw"]:
    df = frames[key]
    if df is None:
        continue
    for col, label in [("user_id", "user_id"), ("username", "username"), ("role", "role"),
                       ("target_tipe", "target_tipe"), ("device", "device")]:
        if col not in df.columns:
            continue
        vc = df[col].value_counts()
        if len(vc) > 60:
            actor_rows.append([key, label, f"[{len(vc)} nilai unik - terlalu banyak, lihat top-20]",
                               "", ""])
            for val, c in vc.head(20).items():
                actor_rows.append([key, f"{label}(top20)", str(val), int(c), pct(int(c), len(df))])
        else:
            for val, c in vc.items():
                actor_rows.append([key, label, str(val), int(c), pct(int(c), len(df))])
write_csv("09_actor_distribution.csv", ["dataset", "column", "value", "count", "percentage"], actor_rows)

# ------------------------------------------------------------ 10 jaringan G/H
net_rows = []
for key in ["synthetic_raw", "retraining_combined_raw"]:
    df = frames[key]
    if df is None:
        continue
    col = "ip_address"
    if col not in df.columns:
        continue
    def classify(v):
        v = str(v)
        if v.startswith("192.168."):
            return "private-192.168"
        if v.startswith(("8.", "20.", "36.", "45.", "66.", "103.", "114.", "139.", "157.", "180.")):
            return "public-generator-prefix"
        if v.startswith(("127.", "::1")) or v == "unknown":
            return "localhost/loopback/unknown"
        try:
            import ipaddress
            o = ipaddress.ip_address(v)
            return "private-lain" if o.is_private else "public-lain"
        except ValueError:
            return "tidak-valid"
    cls = df[col].map(classify)
    for val, c in cls.value_counts().items():
        net_rows.append([key, "ip_category", str(val), int(c), pct(int(c), len(df))])
    uniq = df[col].nunique()
    net_rows.append([key, "ip_unique_count", f"{uniq} alamat unik dari {len(df)} baris", "", ""])
if canonical is not None and "ip_address" in canonical.columns:
    for val, c in canonical["ip_address"].value_counts().items():
        net_rows.append(["retraining_canonical", "ip_address(encoded/category)", str(val), int(c),
                         pct(int(c), len(canonical))])
write_csv("10_network_distribution.csv", ["dataset", "aspect", "value", "count", "percentage"], net_rows)

# --------------------------------------------- 11 file/path/hash audit H
HASH_RE = re.compile(r"file|path|hash|checksum|sha|size|ukuran|berkas_file|cover", re.IGNORECASE)
hash_rows = []
for key, df in frames.items():
    if df is None:
        hash_rows.append([key, "-", "TIDAK ADA atribut file/path/hash", "", "", "", "",
                          "kolom dataset tidak memuat atribut integritas berkas"])
        continue
    hits = [c for c in df.columns if HASH_RE.search(str(c))]
    if not hits:
        hash_rows.append([key, "-", "TIDAK ADA atribut file/path/hash", "", "", "", "",
                          f"kolom tersedia: {', '.join(map(str, df.columns))[:200]}"])
        continue
    for col in hits:
        s = df[col]
        missing = int(s.isna().sum())
        dupes = int(s.duplicated(keep=False).sum())
        hash_rows.append([key, col, "ADA", len(df), missing,
                          f"duplicate_non_null={dupes}",
                          f"unique={int(s.nunique(dropna=True))}",
                          f"contoh={str(s.dropna().iloc[0])[:60]}" if missing < len(df) else ""])

# verifikasi rantai hash di database produksi (SELECT-only + ROLLBACK)
db_status = "GAGAL KONEKSI"
db_json = {}
try:
    import psycopg2
    conn = psycopg2.connect(host="localhost", port=5432, dbname="sistem_arsip_digital",
                            user="postgres", password="qethipen29", connect_timeout=5)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), MIN(waktu), MAX(waktu), COUNT(DISTINCT user_id) FROM audit_log")
    cnt, tmin, tmax, nusers = cur.fetchone()
    cur.execute("SELECT COUNT(*) FROM audit_log WHERE hash_entri IS NULL OR hash_entri NOT SIMILAR TO '[0-9a-f]{64}'")
    bad_hash = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM audit_log WHERE hash_sebelumnya IS NULL")
    null_prev = cur.fetchone()[0]
    cur.execute("SELECT DISTINCT aksi FROM audit_log ORDER BY 1")
    aksi = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT ip_address, COUNT(*) FROM audit_log GROUP BY 1 ORDER BY 2 DESC LIMIT 10")
    ips = [[r[0], int(r[1])] for r in cur.fetchall()]
    conn.rollback()
    conn.close()
    db_status = "OK (read-only)"
    db_json = {"row_count": int(cnt), "timestamp_min": str(tmin), "timestamp_max": str(tmax),
               "distinct_users": int(nusers), "invalid_or_null_hash_entri": int(bad_hash),
               "null_hash_sebelumnya": int(null_prev), "distinct_aksi": aksi, "top_ip": ips}
    hash_rows.append(["postgresql_audit_log(tabel live)", "hash_entri,hash_sebelumnya", "ADA (hash chaining)",
                      int(cnt), int(bad_hash), f"hash_sebelumnya NULL={null_prev}",
                      "rantai SHA-256 per entri", f"rentang waktu {tmin} s/d {tmax}"])
except Exception as exc:  # noqa: BLE001
    db_json = {"error": repr(exc)}
    hash_rows.append(["postgresql_audit_log(tabel live)", "hash_entri,hash_sebelumnya",
                      "TIDAK DAPAT DIVERIFIKASI", "", "", "", "", repr(exc)[:120]])
(OUT / "db_check.json").write_text(json.dumps(db_json, indent=2, default=str), encoding="utf-8")
print("[OK] db_check.json:", db_status)

write_csv("11_file_integrity_audit.csv",
          ["dataset", "attribute", "availability", "record_count_with_attr", "missing",
           "duplicate_summary", "unique_or_chain_summary", "notes"], hash_rows)

# ------------------------------------------- 12 verifikasi klaim Stage 5 I
claims = []
meta = json.loads((SVC / "dataset" / "preprocessed" / "preprocessing_metadata.json").read_text(encoding="utf-8"))
xtr = np.load(SVC / "dataset" / "preprocessed" / "X_train.npy", mmap_mode="r")


def add_claim(claim, evidence, actual, status):
    claims.append([claim, evidence[:400], actual[:400], status])


add_claim("Synthetic = 15000 baris",
          "audit A: len(audit_log_dataset.csv)",
          f"aktual = {n_main}",
          "CONFIRMED" if n_main == 15000 else "NOT_CONFIRMED")
db_cnt = db_json.get("row_count")
add_claim("Real PostgreSQL = 329 baris",
          "stage5 report vs db_check.json (COUNT(*) saat audit)",
          f"laporan lama = 329; aktual saat audit = {db_cnt if db_cnt is not None else 'tidak dapat diverifikasi'}",
          "PARTIALLY_CONFIRMED" if db_cnt == 329 else ("NOT_CONFIRMED" if db_cnt is not None else "NOT_VERIFIABLE"))
comb_n = 0 if combined is None else len(combined)
add_claim("Combined = 15329 baris",
          "stage5 report vs len(retraining_dataset_combined_raw.csv)",
          f"aktual = {comb_n}", "CONFIRMED" if comb_n == 15329 else "NOT_CONFIRMED")
add_claim("9 fitur VAE",
          "preprocessing_metadata.json feature_count; shape X_train.npy; preprocessing_contract.FEATURE_COLUMNS",
          f"metadata={meta.get('feature_count')}; X_train.npy shape={list(xtr.shape)}; kontrak=9",
          "CONFIRMED" if meta.get("feature_count") == 9 and list(xtr.shape)[1] == 9 else "NOT_CONFIRMED")
dc_full = int(combined.duplicated().sum()) if combined is not None else None
add_claim("Duplicate combined = 0",
          "df.duplicated().sum() pada retraining_dataset_combined_raw.csv",
          f"aktual = {dc_full}", "CONFIRMED" if dc_full == 0 else "NOT_CONFIRMED")
loc_cnt = ""
if combined is not None and "ip_category" in combined.columns:
    loc_cnt = int((combined["ip_category"] == "Localhost / Loopback").sum())
elif combined is not None:
    cand = [c for c in combined.columns if "ip" in c.lower() and "cat" in c.lower()]
    loc_cnt = int((combined[cand[0]] == "Localhost / Loopback").sum()) if cand else "kolom kategori IP tidak ditemukan"
add_claim("Localhost = 329 baris di combined",
          "kolom kategori IP pada retraining_dataset_combined_raw.csv",
          f"aktual = {loc_cnt}",
          "CONFIRMED" if loc_cnt == 329 else ("NOT_CONFIRMED" if isinstance(loc_cnt, int) else "NOT_VERIFIABLE"))
leak_cols = [c for c in (combined.columns if combined is not None else [])
             if c.lower() in ("is_anom", "anomaly_type", "risk_level", "skor_anomali", "tingkat_risiko")]
canon_cols = [] if canonical is None else list(canonical.columns)
add_claim("Feature leakage tidak ada (label bukan fitur)",
          "kolom retraining_dataset_canonical.csv vs FEATURE_COLUMNS kontrak",
          f"kolom canonical = {canon_cols}; kolom label di canonical = {[c for c in canon_cols if c.lower() in ('is_anom','anomaly_type','risk_level')] or 'tidak ada'}",
          "CONFIRMED" if canonical is not None and not any(c.lower() in ("is_anom", "anomaly_type", "risk_level") for c in canon_cols) else "PERLU VERIFIKASI")
add_claim("Model/threshold tidak disentuh Stage 5",
          "models/deployment_config.json & models/vae_model.pth mtime vs artefak retraining/",
          "dibandingkan pada 13_consistency_audit.md (waktu modifikasi file)", "LIHAT LAPORAN MD")
write_csv("12_stage5_claim_verification.csv",
          ["claim", "evidence", "actual_result", "status"], claims)

print(json.dumps({"db_status": db_status, "rows": {k: (0 if v is None else len(v)) for k, v in frames.items()}},
                 indent=2))
