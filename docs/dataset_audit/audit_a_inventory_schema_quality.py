# -*- coding: utf-8 -*-
"""TAHAP 1 - Audit forensik bagian A (READ-ONLY).

Menghasilkan: 01_dataset_inventory.csv, 04_schema_audit.csv, 05_quality_audit.csv,
serta audit_summary.json untuk dipakai bagian B.
Tidak mengubah dataset / source code / model / database.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
OUT = Path(__file__).resolve().parent

DATASETS = {
    "synthetic_raw": SVC / "dataset" / "generator" / "raw" / "audit_log_dataset.csv",
    "retraining_combined_raw": SVC / "dataset" / "retraining" / "retraining_dataset_combined_raw.csv",
    "retraining_canonical": SVC / "dataset" / "retraining" / "retraining_dataset_canonical.csv",
    "legacy_sample_vae": SVC / "dataset" / "dataset_vae.csv",
    "processed_train": SVC / "dataset" / "processed" / "train.csv",
    "processed_validation": SVC / "dataset" / "processed" / "validation.csv",
    "processed_test": SVC / "dataset" / "processed" / "test.csv",
}
NPY_FILES = {
    "X_train_preprocessed": SVC / "dataset" / "preprocessed" / "X_train.npy",
    "X_train_candidate": SVC / "dataset" / "retraining" / "X_train_candidate.npy",
}

# Aturan label dari ai-service/dataset/generator/anomaly.py + generate_dataset.py
RISK_FOR_ANOMALY = {
    "login_luar_jam": "Low", "ip_berubah": "Low", "device_berubah": "Low",
    "durasi_tidak_wajar": "Medium", "aktivitas_terlalu_cepat": "Medium",
    "peminjaman_massal": "High", "verifikasi_massal": "High", "Normal": "Normal",
}
NORMAL_DEVICES = {"Windows", "Laptop Windows", "PC Windows", "Android", "iPhone"}
ANOMALY_DEVICES = {"Linux", "MacOS", "Unknown Device", "Virtual Machine"}
EXTERNAL_PREFIXES = ("8.", "20.", "36.", "45.", "66.", "103.", "114.", "139.", "157.", "180.")
WORKFLOW_ACTIVITIES = {
    "Login", "Logout", "Dashboard", "Kelola User", "Kelola Kode Klasifikasi",
    "Lihat Perkara", "Lihat Berkas", "Input Berkas", "Verifikasi", "Cari Berkas",
}
PREP_USE = {
    "timestamp": ("ya (ekstraksi hour/day_of_week lalu drop)", "tidak (turunannya ya)", "tidak"),
    "session_id": ("tidak (drop)", "tidak", "tidak"),
    "user_id": ("ya", "ya", "tidak"),
    "username": ("tidak (drop)", "tidak", "metadata aktor"),
    "role": ("tidak (drop)", "tidak", "metadata aktor"),
    "activity": ("ya (LabelEncoder)", "ya", "tidak"),
    "status": ("ya (LabelEncoder)", "ya", "tidak"),
    "ip_address": ("ya (konversi ke integer)", "ya", "tidak"),
    "device": ("ya (LabelEncoder)", "ya", "tidak"),
    "duration_ms": ("ya (StandardScaler)", "ya", "tidak"),
    "object_count": ("ya (StandardScaler)", "ya", "tidak"),
    "risk_level": ("tidak (drop)", "tidak", "label sintetis (drop)"),
    "anomaly_type": ("tidak (drop)", "tidak", "label sintetis ground-truth (drop)"),
}


def load_csv(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, na_values=[""])


def pct(n, d):
    return round(100.0 * n / d, 4) if d else 0.0


def write_csv(name, header, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"[OK] {name} ({len(rows)} baris)")


frames = {}
for key, path in DATASETS.items():
    frames[key] = load_csv(path)
    n = 0 if frames[key] is None else len(frames[key])
    print(f"[LOAD] {key}: rows={n}")

main = frames["synthetic_raw"]
combined = frames["retraining_combined_raw"]
canonical = frames["retraining_canonical"]

# ---------------------------------------------------------------- 01 inventory
GEN = {
    "synthetic_raw": "ai-service/dataset/generator/generate_dataset.py (random.seed=42)",
    "retraining_combined_raw": "ai-service/prepare_retraining_dataset.py (Stage 5 - artefak lama)",
    "retraining_canonical": "ai-service/prepare_retraining_dataset.py (Stage 5 - artefak lama)",
    "legacy_sample_vae": "tidak ditemukan generator di repo (artefak lama/manual)",
    "processed_train": "tidak ditemukan (placeholder kosong)",
    "processed_validation": "tidak ditemukan (placeholder kosong)",
    "processed_test": "tidak ditemukan (placeholder kosong)",
}
USED_BY = {
    "synthetic_raw": "preprocessing.py -> dataset/preprocessed/X_train.npy -> train_vae_pytorch.py (AKTIF)",
    "retraining_combined_raw": "TIDAK dipakai pipeline aktif (kandidat Stage 5, tidak pernah diretrain)",
    "retraining_canonical": "TIDAK dipakai pipeline aktif (kandidat Stage 5, tidak pernah diretrain)",
    "legacy_sample_vae": "TIDAK dipakai runtime (config.py DATASET_PATH default tidak dibaca kode aktif)",
    "processed_train": "TIDAK dipakai (file 0 byte)",
    "processed_validation": "TIDAK dipakai (file 0 byte)",
    "processed_test": "TIDAK dipakai (file 0 byte)",
}
TYPE = {
    "synthetic_raw": "raw/synthetic",
    "retraining_combined_raw": "derived/synthetic+real-gabungan (artefak lama)",
    "retraining_canonical": "derived/canonical-9-fitur (artefak lama)",
    "legacy_sample_vae": "sample/legacy",
    "processed_train": "placeholder kosong",
    "processed_validation": "placeholder kosong",
    "processed_test": "placeholder kosong",
}
inv = []
for key, path in DATASETS.items():
    df = frames[key]
    inv.append([
        key, path.relative_to(REPO).as_posix(), "CSV",
        0 if df is None else len(df), 0 if df is None else len(df.columns),
        TYPE[key], GEN[key], GEN[key], USED_BY[key],
        "KOSONG (0 byte)" if df is None else "ADA", "",
    ])
for key, path in NPY_FILES.items():
    arr = np.load(path, mmap_mode="r")
    used = ("train_vae_pytorch.py -> models/vae_model.pth (AKTIF)" if key == "X_train_preprocessed"
            else "TIDAK dipakai pipeline aktif (kandidat Stage 5)")
    inv.append([key, path.relative_to(REPO).as_posix(), "NPY", int(arr.shape[0]),
                int(arr.shape[1]) if arr.ndim == 2 else 0,
                "intermediate/matriks fitur", "hasil transformasi preprocessing", "-", used,
                "ADA", f"dtype={arr.dtype} shape={tuple(arr.shape)}"])
inv += [
    ["label_encoders.pkl", "ai-service/dataset/preprocessed/label_encoders.pkl", "PKL", "", "",
     "intermediate/artefak", "preprocessing.py", "preprocessing.py",
     "utils/preprocessing.py (inference AKTIF)", "ADA", ""],
    ["scaler.pkl", "ai-service/dataset/preprocessed/scaler.pkl", "PKL", "", "",
     "intermediate/artefak", "preprocessing.py", "preprocessing.py",
     "utils/preprocessing.py (inference AKTIF)", "ADA", ""],
    ["candidate_scaler.pkl", "ai-service/dataset/retraining/candidate_scaler.pkl", "PKL", "", "",
     "intermediate/artefak (lama)", "prepare_retraining_dataset.py", "prepare_retraining_dataset.py",
     "TIDAK dipakai pipeline aktif", "ADA", ""],
    ["candidate_encoders.pkl", "ai-service/dataset/retraining/candidate_encoders.pkl", "PKL", "", "",
     "intermediate/artefak (lama)", "prepare_retraining_dataset.py", "prepare_retraining_dataset.py",
     "TIDAK dipakai pipeline aktif", "ADA", ""],
]
write_csv("01_dataset_inventory.csv",
          ["dataset_name", "path", "format", "row_count", "column_count", "dataset_type",
           "source", "generated_by", "used_by", "status", "notes"], inv)

# ------------------------------------------------------------------ 04 schema
def dtype_of(s: pd.Series) -> str:
    drop = s.dropna()
    try:
        num = pd.to_numeric(drop.head(200))
        if len(num):
            return "integer" if bool((num == num.astype(int)).all()) else "float"
    except (ValueError, TypeError):
        pass
    try:
        if len(pd.to_datetime(drop.head(50), errors="raise")):
            return "datetime-string"
    except (ValueError, TypeError):
        pass
    return "string/kategorikal"


schema_rows = []
for key in ["synthetic_raw", "retraining_combined_raw", "retraining_canonical", "legacy_sample_vae"]:
    df = frames[key]
    if df is None:
        continue
    n = len(df)
    for col in df.columns:
        s = df[col]
        missing = int(s.isna().sum())
        dt = dtype_of(s)
        if key == "synthetic_raw":
            prep, feat, lab = PREP_USE.get(col, ("perlu verifikasi", "perlu verifikasi", "perlu verifikasi"))
        else:
            prep = feat = lab = "perlu verifikasi (artefak lama)"
        role = ("identifier" if col in ("id", "user_id", "session_id")
                else "timestamp" if col == "timestamp"
                else "fitur VAE" if feat == "ya"
                else "label/metadata" if lab != "perlu verifikasi"
                else "metadata")
        example = "" if missing == n else str(s.dropna().iloc[0])[:80]
        schema_rows.append([key, col, dt, n, missing, pct(missing, n),
                            int(s.nunique(dropna=True)), example,
                            "numerik" if dt in ("integer", "float") else "kategorikal",
                            prep, feat, lab, role])
write_csv("04_schema_audit.csv",
          ["dataset", "column_name", "data_type", "record_count", "missing_count", "missing_pct",
           "unique_count", "example_value", "kind", "used_in_preprocessing",
           "used_as_vae_feature", "used_as_label_or_eval", "role"], schema_rows)

# ----------------------------------------------------------------- 05 quality
q = []
n_main = len(main)
ts = pd.to_datetime(main["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")

dup_full = int(main.duplicated().sum())
q.append(["duplicate_row_penuh", "*", dup_full, pct(dup_full, n_main), "info" if dup_full == 0 else "medium",
          "", "baris identik pada seluruh kolom"])

g = main.groupby("session_id")
cu = int((g["user_id"].nunique() > 1).sum())
cr = int((g["role"].nunique() > 1).sum())
nsess = int(main["session_id"].nunique())
q.append(["session_id_multi_user", "session_id,user_id", cu, pct(cu, nsess), "high" if cu else "info",
          "", f"dari {nsess} session_id unik"])
q.append(["session_id_multi_role", "session_id,role", cr, pct(cr, nsess), "high" if cr else "info",
          "", f"dari {nsess} session_id unik"])

bad_sid = int((~main["session_id"].str.fullmatch(r"S[0-9A-F]{16}")).sum())
q.append(["format_session_id_tidak_valid", "session_id", bad_sid, pct(bad_sid, n_main),
          "medium" if bad_sid else "info", "", "pola harapan S+16 hex dari generator/utils.py"])

bad_ts = int(ts.isna().sum())
q.append(["format_timestamp_tidak_valid", "timestamp", bad_ts, pct(bad_ts, n_main),
          "critical" if bad_ts else "info", "", "pola harapan YYYY-MM-DD HH:MM:SS"])

for col in main.columns:
    m = int(main[col].isna().sum()) + int((main[col].astype(str).str.strip() == "").sum())
    if m:
        q.append(["missing_atau_kosong", col, m, pct(m, n_main), "high", "", "termasuk string kosong"])

valid_ip = main["ip_address"].map(lambda v: bool(re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", str(v))))
bad_ip = int((~valid_ip).sum())
q.append(["format_ip_tidak_valid", "ip_address", bad_ip, pct(bad_ip, n_main),
          "high" if bad_ip else "info", "", "bukan IPv4 dotted-quad"])

mism = main[main.apply(lambda r: RISK_FOR_ANOMALY.get(r["anomaly_type"]) != r["risk_level"], axis=1)]
ex = "; ".join(f"anomaly={r.anomaly_type}/risk={r.risk_level}" for r in mism.head(3).itertuples())
q.append(["inkonsistensi_anomaly_vs_risk", "anomaly_type,risk_level", len(mism), pct(len(mism), n_main),
          "high" if len(mism) else "info", ex, "pemetaan mengikuti generator/anomaly.py"])

llj = ts[main["anomaly_type"] == "login_luar_jam"]
llj_bad = int((llj.dt.hour >= 7).sum())
tot_llj = int((main["anomaly_type"] == "login_luar_jam").sum())
q.append(["login_luar_jam_tapi_jam_kerja", "anomaly_type,timestamp", llj_bad, pct(llj_bad, max(tot_llj, 1)),
          "high" if llj_bad else "info", "", "baris berlabel login_luar_jam dengan jam >= 07:00"])

norm_mask = main["anomaly_type"] == "Normal"
norm_n = int(norm_mask.sum())
early = int((ts[norm_mask].dt.hour < 7).sum())
late = int((ts[norm_mask].dt.hour > 19).sum())
q.append(["normal_sebelum_jam_07", "anomaly_type,timestamp", early, pct(early, norm_n),
          "high" if early else "info", "", "baris berlabel Normal dengan jam < 07:00"])
q.append(["normal_setelah_jam_19", "anomaly_type,timestamp", late, pct(late, norm_n),
          "medium" if late else "info", "", "sesi normal generator maks mulai 17:00 + ~12 menit"])

ext_norm = int((norm_mask & main["ip_address"].map(lambda v: str(v).startswith(EXTERNAL_PREFIXES))).sum())
q.append(["normal_dengan_ip_eksternal", "anomaly_type,ip_address", ext_norm, pct(ext_norm, norm_n),
          "high" if ext_norm else "info", "", "baris Normal memakai prefix IP eksternal milik skenario ip_berubah"])

dev_norm_bad = int((norm_mask & ~main["device"].isin(NORMAL_DEVICES)).sum())
q.append(["normal_dengan_device_anomali", "anomaly_type,device", dev_norm_bad, pct(dev_norm_bad, norm_n),
          "high" if dev_norm_bad else "info", "", "baris Normal memakai device dari daftar anomali"])

dur = pd.to_numeric(main["duration_ms"], errors="coerce")
obj = pd.to_numeric(main["object_count"], errors="coerce")
q += [
    ["durasi_non_numerik", "duration_ms", int(dur.isna().sum()), pct(int(dur.isna().sum()), n_main),
     "high" if dur.isna().any() else "info", "", ""],
    ["durasi_kurang_dari_sama_dengan_nol", "duration_ms", int((dur <= 0).sum()), pct(int((dur <= 0).sum()), n_main),
     "medium" if bool((dur <= 0).any()) else "info", "", "generator mensintesis >= 300 ms"],
    ["object_count_non_numerik", "object_count", int(obj.isna().sum()), pct(int(obj.isna().sum()), n_main),
     "high" if obj.isna().any() else "info", "", ""],
    ["object_count_kurang_dari_sama_dengan_nol", "object_count", int((obj <= 0).sum()), pct(int((obj <= 0).sum()), n_main),
     "medium" if bool((obj <= 0).any()) else "info", "", ""],
]

bad_dev = main[~main["device"].isin(NORMAL_DEVICES | ANOMALY_DEVICES)]
q.append(["nilai_device_di_luar_kamus", "device", len(bad_dev), pct(len(bad_dev), n_main),
          "high" if len(bad_dev) else "info", ", ".join(sorted(set(bad_dev['device']))[:5]), ""])
bad_status = main[~main["status"].isin({"Berhasil", "Gagal"})]
q.append(["nilai_status_di_luar_kamus", "status", len(bad_status), pct(len(bad_status), n_main),
          "high" if len(bad_status) else "info", "", "generator hanya menulis Berhasil/Gagal"])
bad_act = main[~main["activity"].isin(WORKFLOW_ACTIVITIES)]
q.append(["nilai_activity_di_luar_workflows", "activity", len(bad_act), pct(len(bad_act), n_main),
          "high" if len(bad_act) else "info", "", "di luar kamus generator/flows.py"])

with io.StringIO(DATASETS["synthetic_raw"].read_text(encoding="utf-8-sig")) as buf:
    rd = csv.reader(buf)
    header = next(rd)
    widths, malformed, first_bad = {}, 0, ""
    for i, row in enumerate(rd):
        if not row:
            continue
        widths[len(row)] = widths.get(len(row), 0) + 1
        if len(row) != len(header):
            malformed += 1
            first_bad = first_bad or f"baris data {i}: {len(row)} kolom"
q.append(["record_struktur_beda", "*", malformed, pct(malformed, n_main),
          "critical" if malformed else "info", first_bad,
          f"lebar baris: {widths}; kolom header: {len(header)}"])

if combined is not None:
    dc = int(combined.duplicated().sum())
    q.append(["duplicate_row_penuh_combined_raw", "*", dc, pct(dc, len(combined)), "info" if dc == 0 else "medium",
              "", "artefak lama retraining_dataset_combined_raw.csv"])
if canonical is not None:
    dq = int(canonical.duplicated().sum())
    q.append(["duplicate_row_penuh_canonical", "*", dq, pct(dq, len(canonical)), "info" if dq == 0 else "medium",
              "", "artefak lama retraining_dataset_canonical.csv"])

write_csv("05_quality_audit.csv",
          ["issue_type", "column", "affected_records", "affected_percentage", "severity", "example", "notes"], q)

summary = {
    "rows": {k: (0 if v is None else len(v)) for k, v in frames.items()},
    "cols": {k: (0 if v is None else len(v.columns)) for k, v in frames.items()},
    "columns": {k: ([] if v is None else list(v.columns)) for k, v in frames.items()},
    "duplicate_full_synthetic": dup_full,
    "duplicate_full_combined": dc if combined is not None else None,
    "duplicate_full_canonical": dq if canonical is not None else None,
    "missing_total_synthetic": int(sum(int(main[c].isna().sum()) for c in main.columns)),
    "quality_issues": len(q),
    "npy_shapes": {},
}
for key, p in NPY_FILES.items():
    summary["npy_shapes"][key] = list(np.load(p, mmap_mode="r").shape)
meta = json.loads((SVC / "dataset" / "preprocessed" / "preprocessing_metadata.json").read_text(encoding="utf-8"))
summary["preprocessing_metadata"] = meta
(OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print("[OK] audit_summary.json")
print(json.dumps(summary["rows"], indent=2))
