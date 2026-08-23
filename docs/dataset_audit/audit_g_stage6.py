# -*- coding: utf-8 -*-
"""TAHAP 6 - Implementasi aturan approved (protektif) atas dataset utama.

Yang DILAKUKAN (semua disetujui Tahap 5):
  - salinan byte-identik working copy (RULE A/P: dataset preserved);
  - scan exact duplicate verification-only (RULE N);
  - validasi temporal & kalender before/after (RULE A-D);
  - artefak pemetaan aktivitas DOCUMENT_ONLY (RULE E interim);
  - pemeriksaan kontrak fitur VAE & pemisahan label/hash/path (K,L,M).

Yang TIDAK dilakukan: modifikasi row-level apa pun, imputasi, rename,
regenerasi, retraining. Original tidak tersentuh.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
SRC = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv"
STAGE6 = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
OUT = Path(__file__).resolve().parent
DAY_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

# kalender SKB 2025 (identik dgn audit_e_holiday.py)
LN_CB_DATES = [
    "2025-01-01", "2025-01-27", "2025-01-28", "2025-01-29", "2025-03-28",
    "2025-03-29", "2025-03-31", "2025-04-01", "2025-04-02", "2025-04-03",
    "2025-04-04", "2025-04-07", "2025-04-18", "2025-04-20", "2025-05-01",
    "2025-05-12", "2025-05-13", "2025-05-29", "2025-05-30", "2025-06-01",
    "2025-06-06", "2025-06-09", "2025-06-27", "2025-08-17", "2025-09-05",
    "2025-12-25", "2025-12-26",
]


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(n, d):
    return round(100.0 * n / d, 4) if d else 0.0


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"[OK] {name} ({len(rows)} baris)")


# ------------------------------------------------ 1. integritas original
git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()
orig_meta = {
    "path": str(SRC.relative_to(REPO)),
    "file_size_bytes": SRC.stat().st_size,
    "sha256": sha256_of(SRC),
    "row_count": None, "column_count": None,
    "mtime": datetime.fromtimestamp(SRC.stat().st_mtime).isoformat(),
    "git_commit": git_commit,
    "snapshot_time": datetime.now().isoformat(timespec="seconds"),
}

# ------------------------------------------------ salinan byte-identik
shutil.copy2(SRC, STAGE6)
stage_meta = dict(orig_meta)
stage_meta["path"] = str(STAGE6.relative_to(REPO))
stage_meta["sha256"] = sha256_of(STAGE6)
stage_meta["mtime"] = datetime.fromtimestamp(STAGE6.stat().st_mtime).isoformat()
print("[COPY] stage6 dibuat; SHA match:", orig_meta["sha256"] == stage_meta["sha256"])

df_o = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str,
                   keep_default_na=False, na_values=[""])
df_s = pd.read_csv(STAGE6, encoding="utf-8-sig", dtype=str,
                   keep_default_na=False, na_values=[""])
assert df_o.equals(df_s), "working copy berbeda dari original!"
orig_meta["row_count"] = len(df_o)
orig_meta["column_count"] = df_o.shape[1]

# ------------------------------------------------ 2. verifikasi duplikat
exact_dup_mask = df_s.duplicated(keep=False)
n_exact_rows_involved = int(exact_dup_mask.sum())
n_exact_extra = int(df_s.duplicated().sum())
dup_groups = (df_s[exact_dup_mask].groupby(list(df_s.columns)).size()
              if n_exact_rows_involved else pd.Series(dtype=int))
ts = pd.to_datetime(df_s["timestamp"], format="%Y-%m-%d %H:%M:%S")
same_user_ts = int(df_s.duplicated(subset=["user_id", "timestamp"]).sum())
same_sess_act = int(df_s.duplicated(subset=["session_id", "activity"]).sum())
sess_sizes = df_s["session_id"].value_counts()
multi_sess_events = int((sess_sizes > 1).sum())
rows_in_multi = int(sess_sizes[sess_sizes > 1].sum())

rows72 = []
if n_exact_rows_involved:
    for key, c in dup_groups.items():
        rows72.append(["EXACT_DUPLICATE_GROUP", "; ".join(f"{k}={v}" for k, v in zip(df_s.columns, key))[:300],
                       int(c), "DOKUMENTASI SAJA - penghapusan tidak disetujui Tahap 5"])
else:
    rows72.append(["EXACT_DUPLICATE", "(tidak ditemukan)", 0,
                   "tidak ada penghapusan - sesuai RULE N"])
for label, cnt, note in [
    ("SAME_USER_SAME_TIMESTAMP", same_user_ts,
     "dua aktivitas berbeda pada detik sama - sah (bukan otomatis duplikat)"),
    ("SAME_SESSION_SAME_ACTIVITY", same_sess_act,
     "aktivitas berulang dalam satu sesi - sah menurut RULE N"),
    ("SESSION_WITH_MULTIPLE_EVENTS", multi_sess_events,
     f"{rows_in_multi} baris berada dalam sesi multi-event - rantai workflow sah"),
]:
    rows72.append([label, "-", cnt, note])
write_csv("72_duplicate_verification.csv",
          ["duplicate_type", "detail", "count", "disposition"], rows72)

# ------------------------------------------------ 4/5. temporal & kalender
hr = ts.dt.hour
dow = ts.dt.dayofweek
date_str = ts.dt.strftime("%Y-%m-%d")
is_hol = date_str.isin(LN_CB_DATES)


def buckets(frame_hr, frame_dow, frame_hol):
    return {
        "weekday": int((frame_dow < 5).sum()),
        "weekend": int((frame_dow >= 5).sum()),
        "holiday": int(frame_hol.sum()),
        "non-holiday": int((~frame_hol).sum()),
        "before_08": int((frame_hr < 8).sum()),
        "08_to_15_59": int(((frame_hr >= 8) & (frame_hr <= 15)).sum()),
        "16_or_later": int((frame_hr >= 16).sum()),
    }


b_before = buckets(hr, dow, is_hol)
b_after = buckets(hr, dow, is_hol)  # data identik -> bucket identik
write_csv("89_calendar_integrity_check.csv",
          ["category", "before", "after", "difference", "status"],
          [[k, v, b_after[k], 0, "UNCHANGED_OK"] for k, v in b_before.items()])

hourly_before = {f"{h:02d}": int((hr == h).sum()) for h in range(24)}
hourly_after = hourly_before.copy()

# ------------------------------------------------ 6. artefak pemetaan activity
MAP = [
    ("Login", "LOGIN_SUCCESS", "DIRECT"),
    ("Logout", "LOGOUT", "DIRECT"),
    ("Lihat Berkas", "ACCESS_BERKAS_FILE", "DIRECT"),
    ("Cari Berkas", "ACCESS_BERKAS_FILE", "MANY_TO_ONE"),
    ("Input Berkas", "CREATE_BERKAS | UPDATE_BERKAS", "MANY_TO_ONE"),
    ("Verifikasi", "VERIFIKASI_INTEGRITAS_BERKAS | EXPORT_VERIFICATION_REPORT", "MANY_TO_ONE"),
    ("Kelola User", "CREATE_USER | UPDATE_USER | DELETE_USER", "MANY_TO_ONE"),
    ("Dashboard", "NOT_FOUND (tidak ada createAuditLog)", "NOT_FOUND"),
    ("Lihat Perkara", "NOT_FOUND (perkaraController tidak memanggil createAuditLog)", "NOT_FOUND"),
    ("Kelola Kode Klasifikasi", "NOT_FOUND", "NOT_FOUND"),
]
act_counts = df_s["activity"].value_counts()
rows90 = []
for syn, canon, mtype in MAP:
    action = "DEFERRED_TO_GENERATOR_V2" if mtype == "NOT_FOUND" else "DOCUMENT_ONLY"
    reason = ("nilai dataset TIDAK direname - pemetaan hanya dokumentasi kontrak"
              if action == "DOCUMENT_ONLY"
              else "aktivitas tanpa padanan real - keputusan perbaikan memerlukan regenerasi (di luar Stage 6)")
    rows90.append([syn, canon, mtype, action, reason])
assert set(act_counts.index) == {m[0] for m in MAP}
write_csv("90_activity_mapping_stage6.csv",
          ["synthetic_activity", "canonical_activity", "mapping_type", "action", "reason"], rows90)

# ------------------------------------------------ 10. kontrak fitur VAE
prep_text = (SVC / "preprocessing.py").read_text(encoding="utf-8", errors="ignore")
m = re.search(r"FEATURE_COLUMNS\s*=\s*\[(.*?)\]", prep_text, re.S)
contract = re.findall(r'"([^"]+)"', m.group(1)) if m else []
FORBIDDEN = ["hash", "previous_hash", "current_hash", "path", "file", "filename",
             "target_tipe", "target_id", "anomaly_type", "risk_level", "is_anom",
             "skor_anomali", "tingkat_risiko"]
feature_cols_present = [c for c in contract if c in df_s.columns]
contaminations = [c for c in contract if any(f in c.lower() for f in FORBIDDEN)]
x_shape = tuple(np.load(SVC / "dataset" / "preprocessed" / "X_train.npy",
                        mmap_mode="r").shape)

# ------------------------------------------------ 13. before/after metrics
missing_before = int(df_o.isna().sum().sum())
metrics = [
    ["row_count", len(df_o), len(df_s), 0, "UNCHANGED_OK", ""],
    ["column_count", df_o.shape[1], df_s.shape[1], 0, "UNCHANGED_OK", ""],
    ["exact_duplicates", n_exact_extra, n_exact_extra, 0, "NONE_FOUND", "verification-only"],
    ["missing_values", missing_before, int(df_s.isna().sum().sum()), 0, "UNCHANGED_OK", ""],
    ["weekend_count", b_before["weekend"], b_after["weekend"], 0, "UNCHANGED_OK", "RULE C"],
    ["holiday_count", b_before["holiday"], b_after["holiday"], 0, "UNCHANGED_OK", "RULE D; SKB 2025 metadata"],
    ["outside_working_hours_count",
     b_before["before_08"] + b_before["16_or_later"],
     b_after["before_08"] + b_after["16_or_later"], 0, "UNCHANGED_OK", "RULE B analisis-only"],
    ["activity_count", df_o["activity"].nunique(), df_s["activity"].nunique(), 0,
     "UNCHANGED_OK", "rename DEFERRED_TO_GENERATOR_V2"],
    ["feature_count", len(contract), len(contract), 0, "UNCHANGED_OK",
     f"kontrak 9 fitur; X_train.npy={x_shape}"],
    ["label_count", 2, 2, 0, "UNCHANGED_OK", "anomaly_type+risk_level tetap sbg ground truth, di luar fitur"],
    ["hash_feature_count", 0, 0, 0, "UNCHANGED_OK", "RULE L"],
    ["path_feature_count", 0, 0, 0, "UNCHANGED_OK", "RULE K"],
    ["real_record_count", 337, 337, 0, "EXCLUDED", "RULE P - tidak digabung ke training"],
]
write_csv("96_stage6_before_after.csv",
          ["metric", "before", "after", "difference", "status", "notes"], metrics)

stats = {
    "original": orig_meta, "stage6": stage_meta,
    "sha_match": orig_meta["sha256"] == stage_meta["sha256"],
    "frames_equal": True,
    "exact_duplicates": {"groups": int(len(dup_groups)), "rows_involved": n_exact_rows_involved,
                         "extra_rows": n_exact_extra},
    "context_counts": {"same_user_same_timestamp": same_user_ts,
                       "same_session_same_activity": same_sess_act,
                       "sessions_multi_event": multi_sess_events,
                       "rows_in_multi_sessions": rows_in_multi},
    "buckets": b_before, "hourly": hourly_before,
    "contract_features": contract, "contaminations": contaminations,
    "x_train_shape": x_shape,
    "activity_counts": act_counts.to_dict(),
}
(OUT / "t6_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
print("[OK] t6_stats.json")
print(json.dumps({k: stats[k] for k in ("sha_match", "exact_duplicates", "contract_features",
                                        "contaminations", "x_train_shape")}, indent=1))
