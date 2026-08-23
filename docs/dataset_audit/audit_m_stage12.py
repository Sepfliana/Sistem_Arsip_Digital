# -*- coding: utf-8 -*-
"""TAHAP 12 - Integration & parity test jalur inference kandidat Stage 11.

Tidak mengubah produksi; hanya membaca artefak dan menguji modul baru
services/inference_stage11.py + regresi jalur lama.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
sys.path.insert(0, str(SVC))

from schemas.predict_request import PredictRequest          # noqa: E402
from schemas.predict_response import PredictResponse        # noqa: E402
from services import inference_stage11 as s11               # noqa: E402
from services.inference_stage11 import (                    # noqa: E402
    FEATURE_COLUMNS, load_stage11_artifacts,
    predict_stage11, preprocess_record_stage11)

FINAL = SVC / "dataset" / "final"
ENC = SVC / "dataset" / "encoded"
S6 = SVC / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
OUT = Path(__file__).resolve().parent
started = datetime.now().isoformat()
results = []


def check(group, name, ok, detail=""):
    results.append([group, name, "PASS" if ok else "FAIL", str(detail)])
    return ok


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


model, threshold, encoders, scaler = load_stage11_artifacts()
check("artifacts", "model_loadable", model is not None)
check("artifacts", "threshold_value", threshold == 3.0499422550201416, threshold)
check("artifacts", "encoders_vocab_10_2_9",
      [len(encoders[k].classes_) for k in ("activity", "status", "device")] == [10, 2, 9], "")
check("artifacts", "scaler_fit_rows_10503",
      getattr(scaler, "n_samples_seen_", None) == 10503, getattr(scaler, "n_samples_seen_", None))
check("artifacts", "scaler_n_features_9",
      getattr(scaler, "n_features_in_", None) == 9, "")
check("feature_order", "tuple_contract", FEATURE_COLUMNS[0] == "user_id"
      and FEATURE_COLUMNS[-1] == "day_of_week" and len(FEATURE_COLUMNS) == 9,
      "|".join(FEATURE_COLUMNS))

# ---------------- E2E single record ----------------------------------------
s6 = pd.read_csv(S6, encoding="utf-8-sig", dtype=str,
                 keep_default_na=False, na_values=[""])


def raw_record(i):
    r = s6.iloc[i]
    return {"user_id": int(r["user_id"]), "aksi": r["activity"],
            "status": r["status"], "device": r["device"],
            "ip_address": r["ip_address"], "durasi_ms": float(r["duration_ms"]),
            "jumlah_objek": float(r["object_count"]), "waktu": r["timestamp"]}


rec0 = raw_record(0)
unscaled0 = preprocess_record_stage11(rec0)
check("e2e", "unscaled_shape_1x9", unscaled0.shape == (1, 9), unscaled0.shape)
check("e2e", "finite_no_nan_inf", bool(np.isfinite(unscaled0).all()), "")
ip_int0 = unscaled0[0, 4]
check("e2e", "ip_not_zero_default", ip_int0 > 0, f"ip_int={int(ip_int0)}")
scaled0 = scaler.transform(unscaled0)
check("e2e", "scaled_shape_dtype", scaled0.shape == (1, 9), scaled0.shape)
resp = predict_stage11(rec0)
try:
    PredictResponse(**resp)
    resp_ok = True
except Exception as exc:  # noqa: BLE001
    resp_ok = False
    print("resp error:", exc)
check("e2e", "prediction_valid_schema", resp_ok and resp["threshold"] == threshold,
      json.dumps({k: resp[k] for k in ("anomaly_score", "is_anomaly", "status")}))

# ---------------- parity vs training-side representation -------------------
uns = pd.read_csv(ENC / "audit_log_dataset_stage9_encoded_unscaled.csv", encoding="utf-8-sig")
meta = {s: pd.read_csv(FINAL / f"{s}_metadata.csv", encoding="utf-8")
        for s in ("train", "validation", "test")}
mats = {s: np.load(FINAL / f"X_{s}_final.npy") for s in meta}

picks = []
for s, m in meta.items():
    anom_idx = m.index[m["anomaly_type"].ne("Normal")][:2].tolist()
    for pos in [0, len(m) // 2, len(m) - 1, *anom_idx]:
        picks.append((s, int(pos)))

parity_fail = 0
for s, pos in picks:
    row_id = int(meta[s].iloc[pos]["row_id"])
    u = preprocess_record_stage11(raw_record(row_id))[0]
    expected_u = uns.iloc[row_id][list(FEATURE_COLUMNS)].to_numpy(dtype="float64")
    if not np.array_equal(u, expected_u):
        parity_fail += 1
        print("unscaled mismatch:", s, pos)
    scaled = scaler.transform(u.reshape(1, -1))
    if not np.allclose(scaled[0], mats[s][pos], atol=1e-6):
        parity_fail += 1
        print("scaled mismatch:", s, pos)
check("parity", f"train_side_representation_identical_{len(picks)}_rows",
      parity_fail == 0, f"rows={len(picks)}, mismatches={parity_fail}")

# ---------------- negative contract tests ----------------------------------
def expect_error(rec, name):
    try:
        preprocess_record_stage11(rec)
        check("contract", name, False, "no error raised")
    except ValueError as exc:
        check("contract", name, True, str(exc)[:80])

expect_error({**rec0, "ip_address": "999.999.1.1"}, "invalid_ipv4_rejected")
expect_error({**rec0, "ip_address": "::1"}, "ipv6_rejected_no_fabrication")
expect_error({**rec0, "aksi": "Klik Sembarang"}, "unknown_activity_rejected")
expect_error({**rec0, "device": "Smart Fridge"}, "unknown_device_rejected")
ok_ip = preprocess_record_stage11({**rec0, "ip_address": "192.168.1.77"})[0, 4]
check("contract", "valid_ipv4_matches_training_encoding",
      ok_ip == float(int(__import__("ipaddress").ip_address("192.168.1.77"))), int(ok_ip))

# ---------------- regression: old production path intact --------------------
from services import inference as old_inf            # noqa: E402
import app as fastapi_app                            # noqa: E402

check("regression", "old_inference_importable", old_inf is not None)
check("regression", "fastapi_app_importable", fastapi_app is not None)
req = PredictRequest(**{k: v for k, v in rec0.items()})
old_resp = old_inf.predict(req)
try:
    PredictResponse(**old_resp)
    old_ok = True
except Exception:  # noqa: BLE001
    old_ok = False
check("regression", "old_endpoint_logic_works",
      old_ok and isinstance(old_resp["is_anomaly"], bool),
      json.dumps({k: old_resp[k] for k in ("anomaly_score", "is_anomaly")}))
prod_cfg = json.loads((SVC / "models" / "deployment_config.json").read_text())
check("production_safety", "deployment_config_unchanged",
      prod_cfg["threshold"] == 3.1496288776397705, prod_cfg["threshold"])

# ---------------- finalize --------------------------------------------------
import csv  # noqa: E402

with (OUT / "t12_checks.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["group", "check", "status", "detail"]] + results)

passed = sum(1 for r in results if r[2] == "PASS")
failed = [r for r in results if r[2] == "FAIL"]
stats12 = {
    "started": started,
    "checks_pass": passed, "checks_fail": len(failed),
    "failures": failed,
    "parity_rows_tested": len(picks),
    "threshold_used": threshold,
    "new_module_sha256": sha256_of(SVC / "services" / "inference_stage11.py"),
    "artifacts": {
        "model": str(s11.MODEL_PATH), "threshold": str(s11.THRESHOLD_PATH),
        "encoders": str(s11.ENCODERS_PATH), "scaler": str(s11.SCALER_PATH)},
    "deployment_readiness": "READY FOR CONTROLLED INTEGRATION" if not failed
                            else "NOT READY",
}
(OUT / "t12_stats.json").write_text(json.dumps(stats12, indent=2), encoding="utf-8")
print(f"[OK] Stage12 checks: {passed} PASS / {len(failed)} FAIL")
for r in failed:
    print("   FAIL:", r[1], r[3])
