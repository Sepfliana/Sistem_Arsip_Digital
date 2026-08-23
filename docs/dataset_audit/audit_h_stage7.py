# -*- coding: utf-8 -*-
"""TAHAP 7 - Validasi dataset hasil perbaikan (READ-ONLY terhadap dataset).

Semua pemeriksaan in-memory / hash. Tidak ada cleaning, imputasi, rename,
penghapusan, encoding ke artefak produksi. Output hanya laporan di folder ini.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
ORIG = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv"
STAGE6 = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
OUT = Path(__file__).resolve().parent

LN_CB_DATES = [
    "2025-01-01", "2025-01-27", "2025-01-28", "2025-01-29", "2025-03-28",
    "2025-03-29", "2025-03-31", "2025-04-01", "2025-04-02", "2025-04-03",
    "2025-04-04", "2025-04-07", "2025-04-18", "2025-04-20", "2025-05-01",
    "2025-05-12", "2025-05-13", "2025-05-29", "2025-05-30", "2025-06-01",
    "2025-06-06", "2025-06-09", "2025-06-27", "2025-08-17", "2025-09-05",
    "2025-12-25", "2025-12-26",
]
EXPECTED_ACTIVITY = {
    "Login": 3595, "Logout": 3595, "Lihat Perkara": 3497, "Cari Berkas": 3236,
    "Lihat Berkas": 261, "Input Berkas": 261, "Verifikasi": 261,
    "Dashboard": 98, "Kelola User": 98, "Kelola Kode Klasifikasi": 98,
}
FEATURES9 = ["user_id", "activity", "status", "device", "ip_address",
             "duration_ms", "object_count", "hour", "day_of_week"]
FORBIDDEN = ["hash", "previous_hash", "current_hash", "path", "file", "filename",
             "target_tipe", "target_id", "anomaly_type", "risk_level", "is_anom",
             "skor_anomali", "tingkat_risiko"]


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([header] + rows)
    print(f"[OK] {name} ({len(rows)} baris)")


sha_o, sha_s = sha256_of(ORIG), sha256_of(STAGE6)

# ---------------------------------------------- 2. file integrity (100)
try:
    STAGE6.read_bytes()[:200000].decode("utf-8-sig")
    enc_ok = True
except UnicodeDecodeError:
    enc_ok = False
df_o = pd.read_csv(ORIG, encoding="utf-8-sig", dtype=str,
                   keep_default_na=False, na_values=[""])
df_s = pd.read_csv(STAGE6, encoding="utf-8-sig", dtype=str,
                   keep_default_na=False, na_values=[""])

checks100 = [
    ["sha256_match", sha_o, sha_s, "PASS" if sha_o == sha_s else "FAIL", ""],
    ["file_readable", "TRUE", "TRUE", "PASS", "dibuka mode binary"],
    ["csv_parseable", "TRUE", "TRUE", "PASS", f"pandas parse OK {df_s.shape}"],
    ["encoding_valid_utf8_sig", "TRUE", str(enc_ok).upper(),
     "PASS" if enc_ok else "FAIL", "head decode"],
    ["row_count", "15000", str(len(df_s)),
     "PASS" if len(df_s) == 15000 else "FAIL", ""],
    ["column_count", "13", str(df_s.shape[1]),
     "PASS" if df_s.shape[1] == 13 else "FAIL", ""],
    ["column_names_match", "|".join(df_o.columns), "|".join(df_s.columns),
     "PASS" if list(df_o.columns) == list(df_s.columns) else "FAIL", ""],
    ["column_order_match", "original", "identik",
     "PASS" if list(df_o.columns) == list(df_s.columns) else "FAIL", ""],
]
write_csv("100_stage7_file_integrity.csv",
          ["check", "expected", "actual", "status", "notes"], checks100)

# ---------------------------------------------- 3. row-level integrity
merged = df_o.merge(df_s, how="outer", indicator=True)
rows_only_o = int((merged["_merge"] == "left_only").sum())
rows_only_s = int((merged["_merge"] == "right_only").sum())
identical = df_o.equals(df_s)

# ---------------------------------------------- 4. duplicate validation (102)
exact_extra = int(df_s.duplicated().sum())
same_user_ts = int(df_s.duplicated(subset=["user_id", "timestamp"]).sum())
same_sess_act = int(df_s.duplicated(subset=["session_id", "activity"]).sum())
sess_sizes = df_s["session_id"].value_counts()
multi_sess = int((sess_sizes > 1).sum())
rows102 = [
    ["EXACT_DUPLICATE_ROWS", exact_extra, "0",
     "PASS" if exact_extra == 0 else "FAIL",
     "tidak dihapus - tidak ada yang perlu dihapus"],
    ["SAME_USER_SAME_TIMESTAMP", same_user_ts, "0", "INFO",
     "sah bila >0 - bukan otomatis duplikat"],
    ["SAME_SESSION_SAME_ACTIVITY", same_sess_act, "0", "INFO",
     "legitimate repeated event"],
    ["MULTI_EVENT_SESSIONS", multi_sess, "3595", "INFO",
     "desain workflow generator"],
]
write_csv("102_stage7_duplicate_validation.csv",
          ["check", "actual_count", "expected_count", "status", "notes"], rows102)

# ---------------------------------------------- 5. temporal validation (103)
ts = pd.to_datetime(df_s["timestamp"], format="%Y-%m-%d %H:%M:%S")
hr = ts.dt.hour
dow = ts.dt.dayofweek
date_str = ts.dt.strftime("%Y-%m-%d")
is_hol = date_str.isin(LN_CB_DATES)
buckets = {
    "total_records": len(df_s),
    "working_hours_08_15": int(((hr >= 8) & (hr <= 15)).sum()),
    "before_08": int((hr < 8).sum()),
    "after_16": int((hr >= 16).sum()),
    "weekday": int((dow < 5).sum()),
    "weekend": int((dow >= 5).sum()),
    "holiday": int(is_hol.sum()),
}
EXPECTED_TEMPORAL = {
    "total_records": 15000, "working_hours_08_15": 11633, "before_08": 1854,
    "after_16": 1513, "weekday": 10802, "weekend": 4198, "holiday": 1124,
}
rows103 = [[k, v, EXPECTED_TEMPORAL[k],
            "PASS" if v == EXPECTED_TEMPORAL[k] else "FAIL",
            "baseline Tahap 3/6"] for k, v in buckets.items()]
write_csv("103_stage7_temporal_validation.csv",
          ["metric", "actual", "expected", "status", "source"], rows103)

# ---------------------------------------------- 6. holiday validation (104)
hol_counts = date_str[is_hol].value_counts()
T3_PER_DATE = {
    "2025-01-01": 53, "2025-01-27": 52, "2025-01-28": 16, "2025-01-29": 34,
    "2025-03-28": 48, "2025-03-29": 42, "2025-03-31": 32, "2025-04-01": 52,
    "2025-04-02": 20, "2025-04-03": 58, "2025-04-04": 38, "2025-04-07": 36,
    "2025-04-18": 50, "2025-04-20": 38, "2025-05-01": 45, "2025-05-12": 28,
    "2025-05-13": 46, "2025-05-29": 40, "2025-05-30": 51, "2025-06-01": 70,
    "2025-06-06": 32, "2025-06-09": 42, "2025-06-27": 48, "2025-08-17": 29,
    "2025-09-05": 50, "2025-12-25": 38, "2025-12-26": 36,
}
rows104 = []
for d in sorted(T3_PER_DATE):
    actual = int(hol_counts.get(d, 0))
    ok = actual == T3_PER_DATE[d]
    rows104.append([d, T3_PER_DATE[d], actual, "PASS" if ok else "FAIL",
                    "kalender SKB 2025; tetap karakteristik - bukan anomali"])
missing_hol = [d for d in T3_PER_DATE if d not in hol_counts.index]
rows104.append(["TOTAL_HOLIDAY_RECORDS", int(is_hol.sum()), 1124,
                "PASS" if int(is_hol.sum()) == 1124 else "FAIL", ""])
rows104.append(["HOLIDAY_DATES_MISSING", len(missing_hol), 0,
                "PASS" if not missing_hol else "FAIL", "; ".join(missing_hol)])
write_csv("104_stage7_holiday_validation.csv",
          ["date", "expected_count", "actual_count", "status", "notes"], rows104)

# ---------------------------------------------- 7. activity validation (105)
act = df_s["activity"].value_counts()
rows105 = []
for a, exp in EXPECTED_ACTIVITY.items():
    got = int(act.get(a, 0))
    rows105.append([a, exp, got, "PASS" if got == exp else "FAIL",
                    "nama tidak diubah; mapping kanonik hanya dokumentasi"])
extra_act = set(act.index) - set(EXPECTED_ACTIVITY)
rows105.append(["VOCABULARY_SIZE", 10, act.size,
                "PASS" if (act.size == 10 and not extra_act) else "FAIL",
                f"aktivitas tak terduga: {sorted(extra_act) or 'tidak ada'}"])
write_csv("105_stage7_activity_validation.csv",
          ["activity", "expected_count", "actual_count", "status", "notes"], rows105)

# ---------------------------------------------- 8. operational features (106)
dur = pd.to_numeric(df_s["duration_ms"])
obj_c = pd.to_numeric(df_s["object_count"])
uid_n = df_s["user_id"].nunique()
dev_n = df_s["device"].nunique()
ip_internal = int(df_s["ip_address"].str.startswith("192.168.").sum())
status_counts = df_s["status"].value_counts().to_dict()
rows106 = [
    ["user_id_unique", "72 (Tahap 1 baseline)", uid_n,
     "PASS" if uid_n == 72 else "WARNING", "snapshot users dev saat generasi"],
    ["device_distinct", "9 (5 normal + 4 anomali)", dev_n,
     "PASS" if dev_n == 9 else "WARNING", ""],
    ["ip_address_internal_192_168", "mayoritas internal", ip_internal, "INFO",
     "sisanya prefix publik sintetis"],
    ["duration_ms_range", "1 s/d 106760 (Tahap 1)",
     f"{int(dur.min())} s/d {int(dur.max())}", "INFO", "mean=%0.2f" % dur.mean()],
    ["object_count_range", "1 s/d 200 (Tahap 1)",
     f"{int(obj_c.min())} s/d {int(obj_c.max())}", "INFO", ""],
    ["status_distribution", "Berhasil/Gagal",
     json.dumps(status_counts), "INFO", "rasio ~97/3"],
]
write_csv("106_stage7_operational_feature_validation.csv",
          ["feature", "expected_baseline", "actual_stage6", "status", "notes"], rows106)

# ---------------------------------------------- 13. preprocessing compatibility
feats = df_s.copy()
feats["hour"] = hr
feats["day_of_week"] = dow
from sklearn.preprocessing import LabelEncoder  # noqa: E402

X = feats[FEATURES9].copy()
for c in ["activity", "status", "device", "ip_address"]:
    X[c] = LabelEncoder().fit_transform(X[c])
Xnum = X.astype("float64").to_numpy()
nan_ct = int(np.isnan(Xnum).sum())
inf_ct = int(np.isinf(Xnum).sum())
compat_ok = Xnum.shape == (15000, 9) and nan_ct == 0 and inf_ct == 0

stats = {
    "sha_original": sha_o, "sha_stage6": sha_s, "frames_identical": bool(identical),
    "rows_original": len(df_o), "rows_stage6": len(df_s),
    "rows_missing": rows_only_o, "rows_added": rows_only_s,
    "rows_changed": 0 if identical else -1,
    "exact_duplicates": exact_extra, "same_user_ts": same_user_ts,
    "same_sess_act": same_sess_act, "multi_sessions": multi_sess,
    "temporal_buckets": buckets, "holiday_total": int(is_hol.sum()),
    "activity_vocab_size": int(act.size),
    "user_id_unique": uid_n, "device_distinct": dev_n,
    "ip_internal": ip_internal, "status_counts": status_counts,
    "duration_min_max_mean": [float(dur.min()), float(dur.max()), float(dur.mean())],
    "object_count_min_max": [float(obj_c.min()), float(obj_c.max())],
    "preproc": {"shape": list(Xnum.shape), "dtype": str(Xnum.dtype),
                "nan": nan_ct, "inf": inf_ct, "ok": bool(compat_ok)},
    "contract_features": FEATURES9,
}
(OUT / "t7_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
print("[OK] t7_stats.json")
print(json.dumps(stats["preproc"]))
