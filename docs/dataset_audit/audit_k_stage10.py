# -*- coding: utf-8 -*-
"""TAHAP 10 - Final VAE dataset assembly.

Deterministik & reproducible; tidak overwrite artefak sumber.
Split: group-based by session_id, seed 42, 70/15/15.
Scaler final: StandardScaler BARU fit HANYA pada train split.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
ENC = SVC / "dataset" / "encoded"
IN_X = ENC / "audit_log_dataset_stage9_encoded_unscaled.csv"
S6 = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
FINAL = SVC / "dataset" / "final"
OUT = Path(__file__).resolve().parent

SEED = 42
FR_TRAIN, FR_VAL = 0.70, 0.15
FEATURES = ["user_id", "activity", "status", "device", "ip_address",
            "duration_ms", "object_count", "hour", "day_of_week"]


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


started = datetime.now().isoformat()
checks = []


def add(name, expected, ok, detail=""):
    checks.append([name, str(expected), "PASS" if ok else "FAIL", str(detail)])
    return ok


sha_x_in = sha256_of(IN_X)
Xu = pd.read_csv(IN_X, encoding="utf-8-sig")
raw = pd.read_csv(S6, encoding="utf-8-sig", dtype=str,
                  keep_default_na=False, na_values=[""])

add("input_rows_15000", 15000, len(Xu) == 15000, len(Xu))
add("input_cols_9", 9, Xu.shape[1] == 9, list(Xu.columns))
add("feature_order_matches_stage9_metadata", "|".join(FEATURES),
    list(Xu.columns) == FEATURES, "|".join(Xu.columns))
add("input_all_numeric", True,
    all(pd.api.types.is_numeric_dtype(Xu[c]) for c in FEATURES), "")
add("input_nan_0", 0, int(Xu.isna().sum().sum()) == 0, int(Xu.isna().sum().sum()))
add("input_inf_0", 0, int(np.isinf(Xu.to_numpy(dtype=float)).sum()) == 0, "")

meta_s9 = json.loads((ENC / "stage9_metadata.json").read_text(encoding="utf-8"))
add("stage9_metadata_feature_order", True,
    meta_s9.get("feature_order") == FEATURES and "label_mappings" in meta_s9, "")
enc_pkl = pickle.load((ENC / "stage9_label_encoders.pkl").open("rb"))
sc9_pkl = pickle.load((ENC / "stage9_scaler.pkl").open("rb"))
add("stage9_encoders_loadable", "10/2/9",
    [len(enc_pkl[k].classes_) for k in ("activity", "status", "device")] == [10, 2, 9],
    ",".join(str(len(enc_pkl[k].classes_)) for k in enc_pkl))
add("stage9_candidate_scaler_loadable", "n_features=9",
    getattr(sc9_pkl, "n_features_in_", None) == 9, "")

# ---------------- alignment raw <-> encoded --------------------------------
add("alignment_user_id", True, bool((Xu["user_id"].astype(str) == raw["user_id"]).all()), "")
add("alignment_activity_codes", True,
    bool((Xu["activity"].astype(int) ==
          raw["activity"].map(meta_s9["label_mappings"]["activity"])).all()), "")
ts = pd.to_datetime(raw["timestamp"], format="%Y-%m-%d %H:%M:%S")
labels = raw[["anomaly_type", "risk_level"]].copy()
is_anom = labels["anomaly_type"].ne("Normal")
sess = raw["session_id"].copy()

# ---------------- group-based split by session_id --------------------------
groups = np.array(sorted(sess.unique()))
rng = np.random.default_rng(SEED)
rng.shuffle(groups)
g = len(groups)
n_tr = int(round(FR_TRAIN * g))
n_va = int(round(FR_VAL * g))
tr_g, va_g, te_g = set(groups[:n_tr]), set(groups[n_tr:n_tr + n_va]), set(groups[n_tr + n_va:])
mask_tr = sess.isin(tr_g).to_numpy()
mask_va = sess.isin(va_g).to_numpy()
mask_te = sess.isin(te_g).to_numpy()
add("split_groups_disjoint", True, not (tr_g & va_g or tr_g & te_g or va_g & te_g),
    f"{n_tr}/{n_va}/{g - n_tr - n_va} groups")
add("split_rows_cover_all_once", 15000,
    int(mask_tr.sum() + mask_va.sum() + mask_te.sum()) == 15000
    and not (mask_tr & mask_va).any() and not (mask_tr & mask_te).any(),
    f"train={int(mask_tr.sum())}, val={int(mask_va.sum())}, test={int(mask_te.sum())}")

Xtr_raw, Xva_raw, Xte_raw = (Xu.to_numpy(dtype="float64")[mask_tr],
                             Xu.to_numpy(dtype="float64")[mask_va],
                             Xu.to_numpy(dtype="float64")[mask_te])

# ---------------- FINAL TRAINING SCALER (fit train only) -------------------
scaler = StandardScaler().fit(Xtr_raw)
scaler_dir = FINAL / "scaler"
scaler_dir.mkdir(parents=True, exist_ok=True)
with (scaler_dir / "final_train_scaler.pkl").open("wb") as f:
    pickle.dump(scaler, f)

mats = {"train": scaler.transform(Xtr_raw).astype(np.float32),
        "validation": scaler.transform(Xva_raw).astype(np.float32),
        "test": scaler.transform(Xte_raw).astype(np.float32)}
FINAL.mkdir(parents=True, exist_ok=True)
np.save(FINAL / "X_train_final.npy", mats["train"])
np.save(FINAL / "X_validation_final.npy", mats["validation"])
np.save(FINAL / "X_test_final.npy", mats["test"])

# ---------------- matrix validation ---------------------------------------
for name_, m in mats.items():
    add(f"{name_}_shape_2d_cols9", "(rows, 9)", m.ndim == 2 and m.shape[1] == 9, m.shape)
    add(f"{name_}_dtype_float32", "float32", m.dtype == np.float32, m.dtype)
    add(f"{name_}_nan_inf_0", "0/0",
        int(np.isnan(m).sum()) == 0 and int(np.isinf(m).sum()) == 0,
        f"{int(np.isnan(m).sum())}/{int(np.isinf(m).sum())}")
    add(f"{name_}_no_constant_feature", True, bool((m.std(axis=0) > 0).all()),
        float(m.std(axis=0).min()))

# ---------------- cross-split leakage --------------------------------------
key = pd.util.hash_pandas_object(Xu, index=False).to_numpy()
tr_k, va_k, te_k = key[mask_tr], key[mask_va], key[mask_te]
cross_tv = len(np.intersect1d(tr_k, va_k))
cross_tt = len(np.intersect1d(tr_k, te_k))
cross_vt = len(np.intersect1d(va_k, te_k))
add("cross_split_exact_row_overlap", 0, cross_tv + cross_tt + cross_vt == 0,
    f"train-val={cross_tv}, train-test={cross_tt}, val-test={cross_vt}")
sess_split_map = pd.DataFrame({"s": sess,
                               "sp": np.where(mask_tr, "train",
                                              np.where(mask_va, "validation", "test"))})
n_multi = int((sess_split_map.groupby("s")["sp"].nunique() > 1).sum())
add("session_id_never_spans_splits", 0, n_multi == 0,
    f"sessions spanning >1 split = {n_multi}")
add("labels_not_in_matrix", True,
    not any(l in FEATURES for l in ("anomaly_type", "risk_level", "is_anom")),
    "matrix built from FEATURES only")

# ---------------- companion metadata CSVs ---------------------------------
comp = pd.DataFrame({
    "row_id": np.arange(len(raw)),
    "timestamp": raw["timestamp"], "user_id": raw["user_id"],
    "activity": raw["activity"], "session_id": sess,
    "anomaly_type": labels["anomaly_type"], "risk_level": labels["risk_level"],
    "split": np.where(mask_tr, "train", np.where(mask_va, "validation", "test"))})
comp[mask_tr].drop(columns="split").to_csv(FINAL / "train_metadata.csv", index=False, encoding="utf-8")
comp[mask_va].drop(columns="split").to_csv(FINAL / "validation_metadata.csv", index=False, encoding="utf-8")
comp[mask_te].drop(columns="split").to_csv(FINAL / "test_metadata.csv", index=False, encoding="utf-8")

# ---------------- report CSVs (137-141) -----------------------------------
with (OUT / "137_stage10_final_matrix_validation.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["check", "expected", "status", "detail"]] + checks)

rows138 = []
for name_, m_ in [("train", mask_tr), ("validation", mask_va), ("test", mask_te)]:
    sub = labels[m_]
    at = sub["anomaly_type"].value_counts().to_dict()
    rows138.append([name_, int(m_.sum()), round(float(m_.mean()), 4),
                    int((~is_anom[m_]).sum()), int(is_anom[m_].sum()),
                    json.dumps(at, ensure_ascii=False),
                    json.dumps(sub["risk_level"].value_counts().to_dict(), ensure_ascii=False)])
with (OUT / "138_stage10_label_distribution.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["split", "rows", "anomaly_ratio", "normal",
                              "anomaly", "anomaly_type_dist", "risk_level_dist"]] + rows138)

hr = ts.dt.hour.to_numpy(); dow = ts.dt.dayofweek.to_numpy()
hol = ts.dt.strftime("%Y-%m-%d").isin(
    ["2025-01-01", "2025-01-27", "2025-01-28", "2025-01-29", "2025-03-28",
     "2025-03-29", "2025-03-31", "2025-04-01", "2025-04-02", "2025-04-03",
     "2025-04-04", "2025-04-07", "2025-04-18", "2025-04-20", "2025-05-01",
     "2025-05-12", "2025-05-13", "2025-05-29", "2025-05-30", "2025-06-01",
     "2025-06-06", "2025-06-09", "2025-06-27", "2025-08-17", "2025-09-05",
     "2025-12-25", "2025-12-26"]).to_numpy()

rows140 = []
for name_, m_ in [("train", mask_tr), ("validation", mask_va), ("test", mask_te)]:
    h_, d_, hl_ = hr[m_], dow[m_], hol[m_]
    rows140.append([name_, int(m_.sum()),
                    int(((h_ >= 8) & (h_ <= 15)).sum()), int((h_ < 8).sum()),
                    int((h_ >= 16).sum()), int((d_ < 5).sum()), int((d_ >= 5).sum()),
                    int(hl_.sum())])
rows140.append(["TOTAL", 15000, int(((hr >= 8) & (hr <= 15)).sum()), int((hr < 8).sum()),
                int((hr >= 16).sum()), int((dow < 5).sum()), int((dow >= 5).sum()),
                int(hol.sum())])
with (OUT / "140_stage10_temporal_split_distribution.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["split", "rows", "working_hours_08_15", "before_08",
                              "after_16", "weekday", "weekend", "holiday"]] + rows140)

rows141 = []
for name_, m_ in mats.items():
    for i, c in enumerate(FEATURES):
        v = m_[:, i].astype("float64")
        rows141.append([name_, c, round(float(v.min()), 4), round(float(v.max()), 4),
                        round(float(v.mean()), 4), round(float(np.median(v)), 4),
                        round(float(v.std()), 4)])
with (OUT / "141_stage10_feature_distribution.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["split", "feature", "min", "max", "mean",
                              "median", "std"]] + rows141)

# ---------------- final metadata + stats ----------------------------------
out_files = {"X_train_final.npy": FINAL / "X_train_final.npy",
             "X_validation_final.npy": FINAL / "X_validation_final.npy",
             "X_test_final.npy": FINAL / "X_test_final.npy"}
checksums = {k: sha256_of(v) for k, v in out_files.items()}
final_meta = {
    "script": "audit_k_stage10.py v1.0", "generated_at": started,
    "seed": SEED, "split_method": "group-based by session_id (rng default_rng(42))",
    "fractions": {"train": FR_TRAIN, "validation": FR_VAL, "test": round(1 - FR_TRAIN - FR_VAL, 2)},
    "groups": {"total_sessions": g, "train": n_tr, "validation": n_va, "test": g - n_tr - n_va},
    "feature_order": FEATURES,
    "input": {"path": str(IN_X), "sha256_unscaled": sha_x_in},
    "final_scaler": {"type": "StandardScaler", "fit_split": "train",
                     "fit_row_count": int(mask_tr.sum()),
                     "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                     "var": scaler.var_.tolist(),
                     "path": str(scaler_dir / "final_train_scaler.pkl")},
    "shapes": {k: list(v.shape) for k, v in mats.items()},
    "dtype": "float32",
    "labels_in_matrix": False,
    "outputs": {k: str(v) for k, v in out_files.items()},
    "output_sha256": checksums,
}
(FINAL / "final_dataset_metadata.json").write_text(json.dumps(final_meta, indent=2), encoding="utf-8")

stats10 = {
    "started": started, "seed": SEED, "input_unscaled_sha256": sha_x_in,
    "groups": final_meta["groups"],
    "rows": {
        nm: int(m.sum())
        for nm, m in (
            ("train", mask_tr),
            ("validation", mask_va),
            ("test", mask_te),
        )
    },
    "anomaly_ratio": {
        nm: round(float(is_anom[m].mean()), 4)
        for nm, m in (
            ("train", mask_tr),
            ("validation", mask_va),
            ("test", mask_te),
        )
    },
    "cross_split_overlap": {"train_validation": cross_tv, "train_test": cross_tt,
                            "validation_test": cross_vt},
    "scaler_fit_rows": int(mask_tr.sum()),
    "checks_pass": sum(1 for c in checks if c[2] == "PASS"),
    "checks_fail": sum(1 for c in checks if c[2] == "FAIL"),
    "output_sha256": checksums,
}
(OUT / "t10_stats.json").write_text(json.dumps(stats10, indent=2), encoding="utf-8")
print("[OK] final artifacts written; checks:",
      f"{stats10['checks_pass']} PASS / {stats10['checks_fail']} FAIL")
for c in checks:
    if c[2] == "FAIL":
        print("   FAIL:", c[0], c[3])
print("rows:", stats10["rows"], "| anomaly_ratio:", stats10["anomaly_ratio"])
print("cross-split overlap:", stats10["cross_split_overlap"])
