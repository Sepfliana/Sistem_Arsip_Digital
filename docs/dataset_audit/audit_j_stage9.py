# -*- coding: utf-8 -*-
"""TAHAP 9 - Encoding & scaling intermediate dataset VAE.

Replikasi persis kontrak TRAINING existing (ai-service/preprocessing.py):
LabelEncoder utk activity/status/device, IP->integer, numerik passthrough,
StandardScaler. Read-only terhadap semua dataset sumber; artefak baru di
ai-service/dataset/encoded/.
"""
from __future__ import annotations

import csv
import hashlib
import ipaddress
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
IN_S8 = SVC / "dataset" / "feature_engineering" / "audit_log_dataset_stage8_features.csv"
S6 = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
ENC_DIR = SVC / "dataset" / "encoded"
OUT = Path(__file__).resolve().parent

S6_SHA = "5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966"
FEATURES = ["user_id", "activity", "status", "device", "ip_address",
            "duration_ms", "object_count", "hour", "day_of_week"]
ENCODER_COLUMNS = ["activity", "status", "device"]  # sama dgn preprocessing.py:35


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


started = datetime.now().isoformat()
sha_s8_before = sha256_of(IN_S8)
sha_s6_now = sha256_of(S6)

df = pd.read_csv(IN_S8, encoding="utf-8-sig", dtype=str,
                 keep_default_na=False, na_values=[""])
orig_cat = {c: df[c].copy() for c in ENCODER_COLUMNS}
orig_ip = df["ip_address"].copy()

out = pd.DataFrame(index=df.index)
out["user_id"] = pd.to_numeric(df["user_id"]).astype("int64")

encoders = {}
for c in ENCODER_COLUMNS:
    le = LabelEncoder()
    out[c] = le.fit_transform(df[c])
    encoders[c] = le

out["ip_address"] = df["ip_address"].map(lambda v: int(ipaddress.ip_address(v))).astype("int64")
for c in ["duration_ms", "object_count", "hour", "day_of_week"]:
    out[c] = pd.to_numeric(df[c]).astype("float64")
out = out[FEATURES]

X = out.to_numpy(dtype="float64")
scaler = StandardScaler()
Xs = scaler.fit_transform(X).astype("float64")
scaled = pd.DataFrame(Xs, columns=FEATURES)

ENC_DIR.mkdir(parents=True, exist_ok=True)
enc_csv = ENC_DIR / "audit_log_dataset_stage9_encoded.csv"
scaled.to_csv(enc_csv, index=False, encoding="utf-8")
unscaled_csv = ENC_DIR / "audit_log_dataset_stage9_encoded_unscaled.csv"
out.to_csv(unscaled_csv, index=False, encoding="utf-8")

with (ENC_DIR / "stage9_label_encoders.pkl").open("wb") as f:
    pickle.dump(encoders, f)
with (ENC_DIR / "stage9_scaler.pkl").open("wb") as f:
    pickle.dump(scaler, f)

mappings = {c: {k: int(v) for k, v in zip(le.classes_, le.transform(le.classes_))}
            for c, le in encoders.items()}

# ---- validasi ------------------------------------------------------------
checks = []
def add(name, expected, ok, detail):
    checks.append([name, expected, "PASS" if ok else "FAIL", str(detail)])

add("row_count", 15000, len(scaled) == 15000, len(scaled))
add("column_count_9", 9, scaled.shape[1] == 9, list(scaled.columns))
add("feature_order_deterministic", "|".join(FEATURES), list(scaled.columns) == FEATURES, "|".join(scaled.columns))
add("all_numeric", "float64", all(str(t) == "float64" for t in scaled.dtypes),
    ",".join(str(t) for t in scaled.dtypes))
nan_ct = int(scaled.isna().sum().sum())
inf_ct = int(np.isinf(Xs).sum())
add("no_nan", 0, nan_ct == 0, nan_ct)
add("no_inf", 0, inf_ct == 0, inf_ct)
dec_ok = all((encoders[c].inverse_transform(out[c].to_numpy().astype(int)) == orig_cat[c].to_numpy()).all()
             for c in ENCODER_COLUMNS)
add("categorical_roundtrip_exact", True, dec_ok, "inverse_transform == original")
ip_rt = out["ip_address"].map(lambda v: str(ipaddress.ip_address(v)))
add("ip_roundtrip_exact", True, bool((ip_rt == orig_ip).all()), "int->str == original")
add("user_id_int_passthrough", True, out["user_id"].dtype == np.int64, str(out["user_id"].dtype))
mean_ok = bool(np.allclose(Xs.mean(axis=0), 0, atol=1e-9))
std_ok = bool(np.allclose(Xs.std(axis=0), 1, atol=1e-9))
add("scaler_mean_zero", True, mean_ok, float(np.abs(Xs.mean(axis=0)).max()))
add("scaler_std_one", True, std_ok, float(np.abs(Xs.std(axis=0) - 1).max()))
forb = ["hash", "path", "file", "target_tipe", "target_id", "anomaly_type",
        "risk_level", "is_anom", "skor_anomali", "tingkat_risiko"]
leak = [t for t in forb for c in FEATURES if t in c.lower()]
add("label_hash_path_leakage", 0, not leak, leak or "none")
sha_s8_after = sha256_of(IN_S8)
add("stage8_source_unchanged", sha_s8_before, sha_s8_after == sha_s8_before, sha_s8_after)
add("stage6_sha_still_constant", S6_SHA, sha_s6_now == S6_SHA, sha_s6_now)

with (OUT / "125_stage9_numeric_validation.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["check", "expected", "status", "detail"]] + checks)

rows128 = []
for i, c in enumerate(FEATURES):
    v = X[:, i]
    note = json.dumps(mappings[c], ensure_ascii=False) if c in mappings else \
        ("IP string -> integer 32-bit (ipaddress)" if c == "ip_address" else
         ("passthrough int" if c == "user_id" else "passthrough float; StandardScaler"))
    rows128.append([c, int(pd.Series(v).nunique()), round(float(v.min()), 4), round(float(v.max()), 4),
                    round(float(v.mean()), 4), round(float(np.median(v)), 4), round(float(v.std()), 4),
                    int(pd.Series(v).isna().sum()), int(np.isinf(v).sum()),
                    round(float(Xs[:, i].min()), 4), round(float(Xs[:, i].max()), 4), note])
with (OUT / "128_stage9_encoding_scaling_statistics.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([
        ["feature_pre_scale", "unique", "min", "max", "mean", "median", "std",
         "nan", "inf", "scaled_min", "scaled_max", "mapping_or_transform"]] + rows128)

sha_out = sha256_of(enc_csv)
meta = {
    "script": "audit_j_stage9.py v1.0",
    "generated_at": started,
    "input_stage8": {"path": str(IN_S8), "sha256": sha_s8_before},
    "input_stage6_sha256": sha_s6_now,
    "feature_order": FEATURES,
    "encoder_columns": ENCODER_COLUMNS,
    "encodings": {
        "activity": "LabelEncoder (alphabetical)", "status": "LabelEncoder",
        "device": "LabelEncoder",
        "ip_address": "int(ipaddress.ip_address()) 32-bit ordinal [training contract]",
        "user_id": "integer passthrough [training & inference contract]",
        "duration_ms": "raw passthrough (log1p = inference-side only, NOT applied)",
        "object_count": "raw passthrough (log1p = inference-side only, NOT applied)",
        "hour": "passthrough", "day_of_week": "passthrough (Monday=0)"},
    "label_mappings": mappings,
    "unknown_policy": "tidak ada unknown pada dataset ini; LabelEncoder tanpa kelas UNKNOWN",
    "scaler": {"type": "StandardScaler", "fit_on": "seluruh 15.000 baris stage8 (preprocessing candidate)",
               "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
               "var": scaler.var_.tolist()},
    "outputs": {"encoded_csv": str(enc_csv), "encoded_sha256": sha_out,
                "unscaled_csv": str(unscaled_csv)},
}
(ENC_DIR / "stage9_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
(OUT / "t9_stats.json").write_text(json.dumps(
    {**{k: meta[k] for k in ("script", "generated_at", "feature_order", "label_mappings")},
     "input_sha256": sha_s8_before, "output_sha256": sha_out,
     "checks_pass": sum(1 for c in checks if c[2] == "PASS"),
     "checks_fail": sum(1 for c in checks if c[2] == "FAIL"),
     "scaled_min": Xs.min(axis=0).tolist(), "scaled_max": Xs.max(axis=0).tolist()},
    indent=2), encoding="utf-8")

print("[OK] encoded:", enc_csv.name, "sha:", sha_out[:16])
for c in checks:
    print("   ", c[2], c[0])
