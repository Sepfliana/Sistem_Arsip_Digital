# -*- coding: utf-8 -*-
"""TAHAP 8 - Feature engineering (dokumentasi + statistik + artefak kanonik).

READ-ONLY terhadap dataset sumber. Tidak ada encoding final, scaling,
labeling, atau perubahan model/generator/source aplikasi.
Output: statistik fitur pra-encoding, artefak kanonik baru di
ai-service/dataset/feature_engineering/, dan bahan laporan 117-121.
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
SRC = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
FE_DIR = SVC / "dataset" / "feature_engineering"
OUT = Path(__file__).resolve().parent

EXPECTED_SHA = "5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966"
RAW_COLUMNS = ["timestamp", "session_id", "user_id", "username", "role",
               "activity", "status", "ip_address", "device", "duration_ms",
               "object_count", "risk_level", "anomaly_type"]
CANONICAL = ["user_id", "activity", "status", "device", "ip_address",
             "duration_ms", "object_count", "hour", "day_of_week"]
FORBIDDEN = ["hash", "previous_hash", "current_hash", "path", "file", "filename",
             "target_tipe", "target_id"]
LABELS = ["anomaly_type", "risk_level", "is_anom", "skor_anomali", "tingkat_risiko"]


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


sha_before = sha256_of(SRC)
raw = pd.read_csv(SRC, encoding="utf-8-sig", dtype=str,
                  keep_default_na=False, na_values=[""])

# ---- derivasi timestamp (konvensi pandas: Monday=0 .. Sunday=6) ----------
ts = pd.to_datetime(raw["timestamp"], format="%Y-%m-%d %H:%M:%S")
hour = ts.dt.hour
dow = ts.dt.dayofweek

num_cols = {}
for c in ["duration_ms", "object_count"]:
    num_cols[c] = pd.to_numeric(raw[c])

feats = pd.DataFrame({
    "user_id": raw["user_id"],
    "activity": raw["activity"],
    "status": raw["status"],
    "device": raw["device"],
    "ip_address": raw["ip_address"],
    "duration_ms": num_cols["duration_ms"],
    "object_count": num_cols["object_count"],
    "hour": hour,
    "day_of_week": dow,
})

# ---- statistik pra-encoding --------------------------------------------
rows120 = []


def num_stats(name, s, note):
    z = int((s == 0).sum())
    rows120.append([name, "numeric", s.nunique(), int(s.isna().sum()), z,
                    float(s.min()), float(s.max()),
                    round(float(s.mean()), 4), float(s.median()),
                    float(s.quantile(.25)), float(s.quantile(.75)),
                    "", "", note])


def cat_stats(name, s, note):
    vc = s.value_counts()
    rows120.append([name, "categorical", int(s.nunique()),
                    int(s.isna().sum()), 0, "", "", "", "", "", "",
                    str(vc.index[0]), int(vc.iloc[0]), note])


cat_stats("user_id", feats["user_id"], "identifier kategorikal; existing pipeline memperlakukan numerik")
cat_stats("activity", feats["activity"], "kosakata sintetis 10 aktivitas")
cat_stats("status", feats["status"], "biner hasil aksi")
cat_stats("device", feats["device"], "kosakata generator")
cat_stats("ip_address", feats["ip_address"], "string IP; training->integer, kontrak inferensi->kategori")
num_stats("duration_ms", feats["duration_ms"], "continuous behavioral")
num_stats("object_count", feats["object_count"], "count behavioral")
num_stats("hour", feats["hour"].astype(float), "derivasi timestamp.dt.hour")
num_stats("day_of_week", feats["day_of_week"].astype(float), "derivasi timestamp.dt.dayofweek (Monday=0)")

with (OUT / "120_stage8_feature_statistics.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([
        ["feature", "type", "unique_count", "missing", "zero_count", "min", "max",
         "mean", "median", "p25", "p75", "top_value", "top_freq", "notes"]] + rows120)
print("[OK] 120_stage8_feature_statistics.csv")

dist = {
    "activity": feats["activity"].value_counts().to_dict(),
    "status": feats["status"].value_counts().to_dict(),
    "device": feats["device"].value_counts().to_dict(),
    "role": raw["role"].value_counts().to_dict(),
    "username_unique": int(raw["username"].nunique()),
    "session_unique": int(raw["session_id"].nunique()),
    "ip_prefix_internal_192168": int(feats["ip_address"].str.startswith("192.168.").sum()),
    "ip_public_examples": sorted(set(feats.loc[~feats["ip_address"].str.startswith("192.168."), "ip_address"]))[:15],
    "ip_distinct": int(feats["ip_address"].nunique()),
    "hour_freq": feats["hour"].value_counts().sort_index().to_dict(),
    "dow_freq": feats["day_of_week"].value_counts().sort_index().to_dict(),
}

# ---- artefak intermediate kanonik (BARU, bukan menimpa Stage 6) ---------
FE_DIR.mkdir(parents=True, exist_ok=True)
fe_out = FE_DIR / "audit_log_dataset_stage8_features.csv"
feats.to_csv(fe_out, index=False, encoding="utf-8")

# ---- validasi kontrak fitur --------------------------------------------
checks = []
checks.append(["stage6_sha_unchanged", EXPECTED_SHA,
               "PASS" if sha_before == EXPECTED_SHA else "FAIL", sha_before])
checks.append(["row_count_15000", "15000",
               "PASS" if len(raw) == 15000 else "FAIL", str(len(raw))])
checks.append(["raw_column_count_13", "13",
               "PASS" if list(raw.columns) == RAW_COLUMNS else "FAIL",
               "|".join(raw.columns)])
checks.append(["canonical_features_available", "9/9",
               "PASS" if all(c in feats.columns for c in CANONICAL) else "FAIL",
               "|".join(CANONICAL)])
leak = [l for l in LABELS if l in CANONICAL]
checks.append(["label_separation", "0 leak",
               "PASS" if not leak else "FAIL", ",".join(leak) or "none"])
forb = [t for t in FORBIDDEN for c in CANONICAL if t in c.lower()]
checks.append(["hash_path_file_separation", "0 leak",
               "PASS" if not forb else "FAIL", ",".join(forb) or "none"])
hour_ok = bool((feats["hour"].to_numpy() == ts.dt.hour.to_numpy()).all())
dow_ok = bool((feats["day_of_week"].to_numpy() == ts.dt.dayofweek.to_numpy()).all())
checks.append(["hour_derived_from_timestamp_no_shift", "TRUE", "PASS" if hour_ok else "FAIL", "dt.hour"])
checks.append(["day_of_week_derived_monday0_sunday6", "TRUE", "PASS" if dow_ok else "FAIL", "dt.dayofweek"])
checks.append(["no_missing_in_canonical", "0",
               "PASS" if int(feats.isna().sum().sum()) == 0 else "FAIL",
               str(int(feats.isna().sum().sum()))])
sha_after = sha256_of(SRC)
checks.append(["source_reread_sha_equal_after_run", sha_before,
               "PASS" if sha_after == sha_before else "FAIL", sha_after])

with (OUT / "121_stage8_contract_checks.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["check", "expected", "status", "detail"]] + checks)

stats = {
    "input": str(SRC), "rows": len(raw), "raw_columns": RAW_COLUMNS,
    "canonical_features": CANONICAL,
    "sha_stage6_before": sha_before, "sha_stage6_after": sha_after,
    "intermediate_artifact": str(fe_out),
    "duration_ms": {k: float(v) for k, v in {
        "min": feats["duration_ms"].min(), "max": feats["duration_ms"].max(),
        "mean": feats["duration_ms"].mean(), "median": feats["duration_ms"].median(),
        "p25": feats["duration_ms"].quantile(.25), "p75": feats["duration_ms"].quantile(.75),
        "zero_count": float((feats["duration_ms"] == 0).sum())}.items()},
    "object_count": {k: float(v) for k, v in {
        "min": feats["object_count"].min(), "max": feats["object_count"].max(),
        "mean": feats["object_count"].mean(), "median": feats["object_count"].median(),
        "zero_count": float((feats["object_count"] == 0).sum())}.items()},
    **{f"dist_{k}": v for k, v in dist.items()},
}
(OUT / "t8_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
print("[OK] intermediate:", fe_out.name)
print("[OK] contract checks:")
for c in checks:
    print("   ", c[2], c[0])
