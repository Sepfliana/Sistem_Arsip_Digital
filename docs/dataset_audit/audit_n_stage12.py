# -*- coding: utf-8 -*-
"""TAHAP 12b - Wiring & endpoint validation test (tanpa database produksi).

Menguji rute FastAPI nyata: /predict-stage11 kandidat + regresi /predict lama,
plus safety hash seluruh artefak produksi/dataset.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SVC = REPO / "ai-service"
sys.path.insert(0, str(SVC))

from fastapi import HTTPException  # noqa: E402

import app as fastapi_app                            # noqa: E402
from schemas.predict_request import PredictRequest   # noqa: E402
from schemas.predict_response import PredictResponse  # noqa: E402

OUT = Path(__file__).resolve().parent
results = []


def check(group, name, ok, detail=""):
    results.append([group, name, "PASS" if ok else "FAIL", str(detail)])
    print(("PASS" if ok else "FAIL"), group, name, str(detail)[:70])
    return ok


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------- wiring -----------------------------------------------------
paths = {getattr(r, "path", "") for r in fastapi_app.app.routes}
check("wiring", "route_predict_exists", "/predict" in paths)
check("wiring", "route_predict_stage11_exists", "/predict-stage11" in paths)

VALID = {"waktu": "2025-03-10 09:15:00", "user_id": 7, "aksi": "Login",
         "status": "Berhasil", "device": "PC Windows",
         "ip_address": "192.168.1.23", "durasi_ms": 1200.0, "jumlah_objek": 1.0}
req = PredictRequest(**VALID)

# candidate endpoint: real route function invocation
r11 = fastapi_app.predict_audit_log_stage11(req)
resp11 = PredictResponse(**r11.model_dump())
check("candidate_endpoint", "valid_request_ok", True)
check("candidate_endpoint", "schema_valid", resp11.anomaly_score == r11.anomaly_score)
check("candidate_endpoint", "threshold_stage11",
      r11.threshold == 3.0499422550201416, r11.threshold)
check("candidate_endpoint", "score_fields_equal",
      r11.anomaly_score == r11.reconstruction_error == r11.score, "")
check("candidate_endpoint", "is_anomaly_bool",
      isinstance(r11.is_anomaly, bool) and r11.status in ("NORMAL", "ANOMALY"),
      f"{r11.is_anomaly}/{r11.status}")

# candidate negative tests -> HTTP 400
def expect_400(payload_overrides, name):
    bad = PredictRequest(**{**VALID, **payload_overrides})
    try:
        fastapi_app.predict_audit_log_stage11(bad)
        check("candidate_negative", name, False, "no HTTPException")
    except HTTPException as exc:
        check("candidate_negative", name, exc.status_code == 400,
              f"{exc.status_code}: {str(exc.detail)[:60]}")

expect_400({"ip_address": "999.999.1.1"}, "invalid_ipv4_http400")
expect_400({"ip_address": "::1"}, "ipv6_http400")
expect_400({"aksi": "Klik Sembarang"}, "unknown_activity_http400")
expect_400({"device": "Smart Fridge"}, "unknown_device_http400")
expect_400({"status": "Mungkin"}, "unknown_status_http400")

# valid public IPv4 also accepted & non-zero path (integer differs from private)
r11b = fastapi_app.predict_audit_log_stage11(
    PredictRequest(**{**VALID, "ip_address": "103.10.20.30"}))
check("candidate_endpoint", "public_ipv4_ok", r11b.anomaly_score >= 0.0, "")

# ---------------- regression: production /predict ---------------------------
old = fastapi_app.predict_audit_log(req)
old_resp = PredictResponse(**old.model_dump())
check("regression_old_predict", "still_works", True)
check("regression_old_predict", "schema_same", old_resp.threshold == old.threshold)
check("regression_old_predict", "uses_production_threshold",
      old.threshold == 3.1496288776397705, old.threshold)

from services import model_loader  # noqa: E402
check("regression_old_predict", "uses_production_model_path",
      str(model_loader.MODEL_PATH).endswith("models" + chr(92) + "vae_model.pth"),
      str(model_loader.MODEL_PATH))

# ---------------- production / dataset safety hashes -------------------------
EXPECT_SHA = {
    "stage6": ("ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv",
               "5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966"),
    "stage8": ("ai-service/dataset/feature_engineering/audit_log_dataset_stage8_features.csv",
               "ce4854fae37d5c5ce4739784554aa9c20a9ff8dbe84f28541d924a47469ef959"),
    "stage9_encoded": ("ai-service/dataset/encoded/audit_log_dataset_stage9_encoded.csv",
                       "63801485f5e5c84dbe4453d214f811de62c75b8efd1e53bb917664303846affc"),
    "X_train_final": ("ai-service/dataset/final/X_train_final.npy",
                      "fe67e6c8bc1e5b4fdbb532a8b8691fba1c96068239689a19573c8625e182a59f"),
    "X_validation_final": ("ai-service/dataset/final/X_validation_final.npy",
                           "f6e5185bf3a0486bcf7f28580a7354f9b64a1d95a6824775a92a933dbb2e2af3"),
    "X_test_final": ("ai-service/dataset/final/X_test_final.npy",
                     "a2d02e16fd76349709bd29bf43242f5d0929f6f847b522b34e7e20e409153bc9"),
}
safety = {}
for key, (rel, expected) in EXPECT_SHA.items():
    actual = sha256_of(REPO / rel)
    safety[key] = actual
    check("safety", f"{key}_unchanged", actual == expected, actual[:16])

prod_model_sha = sha256_of(SVC / "models" / "vae_model.pth")
dep_cfg = json.loads((SVC / "models" / "deployment_config.json").read_text())
check("safety", "deployment_config_unchanged",
      dep_cfg["threshold"] == 3.1496288776397705, dep_cfg["threshold"])
safety["vae_model_production"] = prod_model_sha

# ---------------- finalize ----------------------------------------------------
import csv  # noqa: E402

with (OUT / "t12b_checks.csv").open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["group", "check", "status", "detail"]] + results)

passed = sum(1 for r in results if r[2] == "PASS")
failed = [r for r in results if r[2] == "FAIL"]
prev = json.loads((OUT / "t12_stats.json").read_text(encoding="utf-8"))
prev["wiring"] = {
    "started": str(prev.get("started")),
    "checks_pass": passed, "checks_fail": len(failed), "failures": failed,
    "endpoint_candidate": "/predict-stage11",
    "production_unchanged": {"deployment_threshold": dep_cfg["threshold"],
                             "vae_model_sha256": prod_model_sha},
    "safety_hashes": safety,
    "rollback": "hapus rute /predict-stage11 di app.py; jalur lama tidak tersentuh",
}
(OUT / "t12_stats.json").write_text(json.dumps(prev, indent=2), encoding="utf-8")
print(f"[OK] Stage12 wiring checks: {passed} PASS / {len(failed)} FAIL")
for r in failed:
    print("   FAIL:", r[1], r[3])
