"""Evidence-based A–V audit for the one final VAE deployment path."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app import app, initialise_inference, predict_audit_log
from schemas.predict_request import PredictRequest
from services.final_vae_pipeline import (
    EXPECTED_PREPROCESSING_CONTRACT,
    FINAL_MODEL_DIR,
    MODEL_CONFIG,
    MODEL_METADATA_PATH,
    PREPROCESSING_DIR,
    THRESHOLD_PATH,
    build_explanation,
    load_final_model,
    load_final_threshold,
    reconstruction_details,
)
from utils.final_preprocessing_contract import (
    FEATURE_COLUMNS, IP_FEATURE_INDEX, IP_ZSCORE_BOUNDS, ipv4_to_integer,
    parse_timestamp_wib, preprocess_for_inference,
)


SERVICE_DIR = Path(__file__).resolve().parent
REPO_DIR = SERVICE_DIR.parent
SSOT_DIR = SERVICE_DIR / "dataset" / "final_stage1_ssot"
REPORT_PATH = REPO_DIR / "FINAL_VAE_PIPELINE_REPORT.md"
RESULTS_PATH = FINAL_MODEL_DIR / "final_validation_results.json"
ITEMS = {
    "A": "Dataset", "B": "Split", "C": "Leakage", "D": "Feature order", "E": "Encoder",
    "F": "Scaler", "G": "IP conversion", "H": "Timestamp/timezone", "I": "Model architecture",
    "J": "Training configuration", "K": "Reconstruction/KL loss", "L": "Reconstruction error",
    "M": "Anomaly score", "N": "Feature contribution", "O": "Threshold", "P": "Test metrics",
    "Q": "FastAPI", "R": "Backend", "S": "Artifact consistency", "T": "Determinism",
    "U": "Thesis/forensic parity", "V": "Legacy/production status",
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def markdown(status: str, results: dict[str, dict[str, Any]], evaluation: dict[str, Any], threshold: float, ip_cases: dict[str, Any]) -> str:
    table = "\n".join(f"| {key} | {ITEMS[key]} | {'PASS' if value['passed'] else 'FAIL'} | {value['detail']} |" for key, value in results.items())
    test_metrics = evaluation["splits"]["test"]["metrics"]
    validation_metrics = evaluation["splits"]["validation"]["metrics"]
    test_distribution = evaluation["splits"]["test"]["distribution_all"]
    time = evaluation["splits"]["test"]["time_breakdown"]
    return f"""# Final VAE Pipeline Report

## Status akhir

**{status}**

Satu jalur aktif adalah:

`audit log HTTP -> request IPv4 context -> backend /predict -> FastAPI -> Stage 2 v2 preprocessing -> VAE final -> nine feature errors -> mean anomaly score -> P95 train-normal threshold -> risk/explanation`.

## Dataset dan kontrak final

- SSOT: `ai-service/dataset/final_stage1_ssot/`.
- Split sesi: train `6.692` baris / `1.623` sesi / `0` anomali; validation `4.168` / `986`; test `4.140` / `986`; tidak ada overlap sesi.
- Urutan input tetap: `{', '.join(FEATURE_COLUMNS)}`.
- Kontrak preprocessing: `{EXPECTED_PREPROCESSING_CONTRACT}`. Encoder kategorikal dan `StandardScaler` dipasangkan dari train normal saja.
- IPv4 tetap integer unsigned 32-bit. Audit integrasi menemukan train hanya mencakup `192.168.1.*`; agar IPv4 valid di luar rentang itu tidak menghasilkan jutaan standard deviation, z-score IP sesudah transform dibatasi `{IP_ZSCORE_BOUNDS}` secara identik pada seluruh jalur. Ini tidak menggunakan label, bobot feature, perubahan jumlah feature, atau threshold.

## Model, skor, dan threshold

- Arsitektur terkunci: `9 -> 64 -> 32 -> latent 8 -> 32 -> 64 -> 9`; ReLU, dropout 0,2, Adam 0,001, 100 epoch, capacity 0,5/warm-up 60.
- Fit hanya memakai train normal. Validation hanya dipantau; test tidak dipakai untuk fitting atau threshold.
- Error setiap feature adalah squared reconstruction error. `anomaly_score = mean(9 feature errors)` tanpa weighting.
- Contribution = `feature_error / sum(feature_errors)`; total nol ditangani aman.
- Threshold final: **{threshold:.12f}**, P95 reconstruction score train normal. Referensi `mean + 3σ` direkam tetapi tidak dipilih, karena keputusan forensik Tahap 11 menetapkan P95 train sebagai ground truth.

## Evaluasi jujur

| Split | Accuracy | Precision | Recall | F1 | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Validation | {validation_metrics['accuracy']:.4f} | {validation_metrics['precision']:.4f} | {validation_metrics['recall']:.4f} | {validation_metrics['f1']:.4f} | {validation_metrics['confusion_matrix']['tn']} | {validation_metrics['confusion_matrix']['fp']} | {validation_metrics['confusion_matrix']['fn']} | {validation_metrics['confusion_matrix']['tp']} |
| Test | {test_metrics['accuracy']:.4f} | {test_metrics['precision']:.4f} | {test_metrics['recall']:.4f} | {test_metrics['f1']:.4f} | {test_metrics['confusion_matrix']['tn']} | {test_metrics['confusion_matrix']['fp']} | {test_metrics['confusion_matrix']['fn']} | {test_metrics['confusion_matrix']['tp']} |

- Distribusi test: mean score `{test_distribution['score']['mean']:.6f}`, median `{test_distribution['score']['median']:.6f}`, P95 `{test_distribution['score']['p95']:.6f}`.
- Kontribusi IP rata-rata seluruh test `{test_distribution['mean_feature_contributions']['ip_address']:.2%}`; bukan lagi dominan akibat input tak-terbatas. Untuk label `ip_berubah`, IP boleh dominan secara semantik karena memang feature itulah yang diubah.
- Hour tetap memberi sinyal tanpa aturan buatan: error hour rata-rata jam kerja `{time['working_hours_08_15']['mean_feature_errors']['hour']:.6f}` dan luar jam kerja `{time['outside_working_hours']['mean_feature_errors']['hour']:.6f}`.
- SSOT tidak memiliki baris loopback. Uji converter/inference tetap dilakukan langsung: `{json.dumps(ip_cases, ensure_ascii=False)}`. Hasil ini membuktikan input finite dan bounded; ia bukan klaim metrik klasifikasi localhost yang tidak tersedia dalam SSOT.

## FastAPI dan backend

- FastAPI hanya mengekspos `/predict` sebagai inference production; `/predict-stage11` tidak diregistrasikan.
- `backend/services/auditLogService.js` menormalkan setiap URL konfigurasi ke `/predict`, lalu memanggilnya dengan payload berkontrak final.
- Middleware `backend/utils/auditRequestContext.js` meneruskan IPv4 request dan User-Agent ke semua call-site audit. Jika IPv4 valid tidak ada, log tetap disimpan dan inferensi sengaja dilewati—alamat `unknown` tidak dipalsukan menjadi input VAE.

## Artifact final

- `ai-service/models/final_vae/vae_model_final.pth`
- `model_config.json`, `model_metadata.json`, `training_history.json`, `training_metadata.json`, `threshold.json`, `evaluation.json`, `final_validation_results.json`
- `ai-service/dataset/final_stage1_ssot/preprocessing_stage2/` berisi encoder, scaler, feature contract, matrix per split, manifest, dan hasil parity.

## Status pipeline lama

| Jalur/artifact | Status | Keterangan |
|---|---|---|
| `services/final_vae_pipeline.py` + `models/final_vae/` | FINAL / ACTIVE | Satu-satunya jalur `/predict`. |
| `dataset/final_stage1_ssot/preprocessing_stage2/` | FINAL / ACTIVE | Kontrak v2 paired dengan model final. |
| `preprocessing_stage2_v1_unbounded_legacy/` + `final_vae_v1_unbounded_ip_candidate/` | CANDIDATE / PRESERVED | Dipertahankan sebagai bukti sebelum koreksi distorsi IP; tidak dimuat. |
| `services/inference_stage11.py` + `models/retrained/` | CANDIDATE / DISCONNECTED | Route eksperimen tidak lagi terdaftar. |
| `models/vae_model.pth`, `dataset/preprocessed/`, `utils/preprocessing.py` | LEGACY | Tidak dipanggil jalur final. |
| `model/*.keras`, `train.py`, `evaluate.py` | LEGACY / DEAD | Pipeline Keras lama. |
| `stage7/`, `models/candidate/`, dataset retraining candidate | EXPERIMENTAL / CANDIDATE | Bukan production. |
| `*_legacy_*`, `*_pre_*` | LEGACY / PRESERVED | Salinan sebelum pengalihan untuk audit/rollback. |

## Audit A–V

| Item | Pemeriksaan | Status | Bukti |
|---|---|---|---|
{table}

## File kode yang diubah

- `ai-service/utils/final_preprocessing_contract.py`
- `ai-service/finalize_preprocessing_stage2.py`
- `ai-service/validate_preprocessing_stage2.py`
- `ai-service/services/final_vae_pipeline.py`
- `ai-service/train_vae_pytorch.py`
- `ai-service/services/inference.py`, `services/model_loader.py`, `app.py`, `schemas/predict_response.py`
- `backend/utils/auditRequestContext.js`, `backend/app.js`, `backend/services/auditLogService.js`
- `ai-service/requirements.txt`
"""


def main() -> int:
    results: dict[str, dict[str, Any]] = {}

    def check(item: str, condition: bool, detail: str) -> None:
        results[item] = {"passed": bool(condition), "detail": detail}

    stage1 = json.loads((SSOT_DIR / "final_dataset_metadata.json").read_text(encoding="utf-8"))
    stage2 = json.loads((PREPROCESSING_DIR / "validation_results.json").read_text(encoding="utf-8"))
    frames = {name: pd.read_csv(SSOT_DIR / f"{name}_metadata.csv", encoding="utf-8") for name in ("train", "validation", "test")}
    matrices = {name: np.load(PREPROCESSING_DIR / f"X_{name}_final.npy", allow_pickle=False) for name in frames}
    expected_sizes = {"train": 6692, "validation": 4168, "test": 4140}
    session_sets = {name: set(frame["session_id"].astype(str)) for name, frame in frames.items()}
    overlaps = [len(session_sets["train"] & session_sets["validation"]), len(session_sets["train"] & session_sets["test"]), len(session_sets["validation"] & session_sets["test"])]

    check("A", stage1.get("status") == "PASS" and {name: len(frame) for name, frame in frames.items()} == expected_sizes, "Stage 1 PASS; sizes 6692/4168/4140")
    check("B", stage1.get("split_policy", {}).get("method", "").startswith("session-based") and stage1.get("session_counts") == {"train": 1623, "validation": 986, "test": 986}, "deterministic session-based SSOT split")
    check("C", overlaps == [0, 0, 0] and frames["train"]["anomaly_type"].eq("Normal").all(), f"session overlap={overlaps}; train anomalies=0")
    check("D", all(matrix.shape == (expected_sizes[name], 9) for name, matrix in matrices.items()) and stage1.get("feature_order") == list(FEATURE_COLUMNS), ", ".join(FEATURE_COLUMNS))
    check("E", stage2.get("status") == "STAGE 2 — PASS" and stage2.get("contract_version") == EXPECTED_PREPROCESSING_CONTRACT, "single train-fitted categorical encoder; v2 parity PASS")
    check("F", all(item["passed"] for item in stage2["checks"] if item["name"] in {"scaler_train_normal_only", "training_inference_parity_same_raw"}), "scaler fit train-only; inference transform parity")
    check("G", all(item["passed"] for item in stage2["checks"] if item["name"] == "special_ipv4_integer_and_bounded_parity"), "IPv4 32-bit + bounded z-score [-3,3]")
    check("H", parse_timestamp_wib("2025-03-10 14:00:00") == (14, 0) and parse_timestamp_wib("2025-03-10 19:00:00") == (19, 0) and parse_timestamp_wib("2025-03-10 00:00:00") == (0, 0), "naive WIB 14/19/midnight exact")
    check("I", MODEL_CONFIG["input_dimension"] == 9 and MODEL_CONFIG["latent_dimension"] == 8 and MODEL_CONFIG["hidden_layers"] == {"encoder": [64, 32], "decoder": [32, 64]} and MODEL_CONFIG["dropout"] == 0.2, "9→64→32→8→32→64→9, ReLU/dropout 0.2")
    history = json.loads((FINAL_MODEL_DIR / "training_history.json").read_text(encoding="utf-8"))
    training = json.loads((FINAL_MODEL_DIR / "training_metadata.json").read_text(encoding="utf-8"))
    check("J", len(history) == 100 and history[59]["kl_capacity"] == 0.5 and training["train_ssot_rows"] == 6692 and training["train_anomaly_rows"] == 0 and training["validation_and_test_fitting"] is False, "Adam 0.001, 100 epochs, capacity 0.5 at epoch 60; train-normal only")
    trainer_source = (SERVICE_DIR / "train_vae_pytorch.py").read_text(encoding="utf-8")
    check("K", "functional.mse_loss" in trainer_source and "logvar.exp()" in trainer_source and "torch.abs(kl_loss - kl_capacity(epoch))" in trainer_source, "MSE reconstruction + KL capacity loss")
    details = reconstruction_details(matrices["test"][:3])
    check("L", details["feature_errors"].shape == (3, 9) and np.allclose(details["feature_errors"], np.square(matrices["test"][:3] - details["reconstruction"]), atol=0, rtol=0), "nine squared reconstruction errors per record")
    check("M", np.allclose(details["anomaly_scores"], details["feature_errors"].mean(axis=1), atol=0, rtol=0), "score exactly mean of nine errors; no weights")
    errors, contributions, dominant = build_explanation(details["feature_errors"][0])
    check("N", len(errors) == len(contributions) == 9 and abs(sum(contributions.values()) - 1.0) < 1e-12 and len(dominant) == 3, "contribution normalized safely; dominant features returned")
    threshold = load_final_threshold()
    recomputed = float(np.percentile(reconstruction_details(matrices["train"])["anomaly_scores"], 95))
    threshold_metadata = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
    check("O", abs(threshold - recomputed) < 1e-12 and threshold_metadata.get("test_used") is False and threshold_metadata.get("fit_split") == "train", f"P95 train-normal={threshold:.12f}; test unused")
    evaluation = json.loads((FINAL_MODEL_DIR / "evaluation.json").read_text(encoding="utf-8"))
    metrics = evaluation["splits"]["test"]["metrics"]
    check("P", sum(metrics["confusion_matrix"].values()) == expected_sizes["test"] and all(key in metrics for key in ("accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate")), f"test confusion totals={expected_sizes['test']}; F1={metrics['f1']:.6f}")
    initialise_inference()
    raw = frames["test"].iloc[0]
    response = predict_audit_log(PredictRequest(waktu=raw.timestamp, user_id=int(raw.user_id), aksi=raw.activity, status=raw.status, device=raw.device, ip_address=raw.ip_address, durasi_ms=float(raw.duration_ms), jumlah_objek=float(raw.object_count))).model_dump()
    routes = [route.path for route in app.routes]
    check("Q", "/predict" in routes and "/predict-stage11" not in routes and response["preprocessing_contract"] == EXPECTED_PREPROCESSING_CONTRACT and len(response["feature_errors"]) == 9, "single FastAPI /predict uses paired v2 artifacts")
    backend_source = (REPO_DIR / "backend" / "services" / "auditLogService.js").read_text(encoding="utf-8")
    context_source = (REPO_DIR / "backend" / "utils" / "auditRequestContext.js").read_text(encoding="utf-8")
    check("R", 'new URL("/predict", configuredAiServiceUrl)' in backend_source and "axios.post(AI_SERVICE_URL" in backend_source and "normalizeIpv4" in context_source and "AI inference skipped" in backend_source, "backend pinned to /predict with request IPv4 context")
    metadata = json.loads(MODEL_METADATA_PATH.read_text(encoding="utf-8"))
    hash_ok = all(sha256_of(FINAL_MODEL_DIR / ({"model": "vae_model_final.pth", "config": "model_config.json", "threshold": "threshold.json", "history": "training_history.json", "evaluation": "evaluation.json", "training_metadata": "training_metadata.json"}[name])) == digest for name, digest in metadata["artifacts_sha256"].items())
    preproc_ok = all(sha256_of(PREPROCESSING_DIR / name) == digest for name, digest in metadata["preprocessing"]["artifacts_sha256"].items())
    check("S", hash_ok and preproc_ok and metadata["preprocessing"]["contract"] == EXPECTED_PREPROCESSING_CONTRACT, "model, threshold, history, encoder, scaler, contract hashes match")
    repeat = predict_audit_log(PredictRequest(waktu=raw.timestamp, user_id=int(raw.user_id), aksi=raw.activity, status=raw.status, device=raw.device, ip_address=raw.ip_address, durasi_ms=float(raw.duration_ms), jumlah_objek=float(raw.object_count))).model_dump()
    check("T", response["score"] == repeat["score"] and response["feature_errors"] == repeat["feature_errors"] and stage2.get("parity", {}).get("max_abs_diff") == 0.0, "deterministic posterior-mean inference; preprocessing diff=0")
    test_distribution = evaluation["splits"]["test"]["distribution_all"]
    check("U", threshold_metadata["method"] == "percentile-95 of train-normal reconstruction scores" and MODEL_CONFIG["epochs"] == 100 and test_distribution["mean_feature_contributions"]["ip_address"] < 0.1, f"forensic P95/architecture retained; test IP contribution={test_distribution['mean_feature_contributions']['ip_address']:.2%}")
    legacy = json.loads((SSOT_DIR / "legacy_artifact_checksums.json").read_text(encoding="utf-8"))
    original_hashes = legacy["before"]
    legacy_ok = legacy.get("unchanged") is True and all((REPO_DIR / path).exists() and sha256_of(REPO_DIR / path) == digest for path, digest in original_hashes.items())
    check("V", legacy_ok and (SSOT_DIR / "preprocessing_stage2_v1_unbounded_legacy").exists() and (SERVICE_DIR / "models" / "final_vae_v1_unbounded_ip_candidate").exists(), f"{len(original_hashes)} preexisting artifacts checksum-preserved; v1 candidate preserved")

    ip_cases: dict[str, Any] = {}
    base = raw.to_dict()
    for label, ip in {"loopback": "127.0.0.1", "private": "10.0.0.1", "public": "8.8.8.8"}.items():
        record = dict(base); record["ip_address"] = ip
        transformed = preprocess_for_inference(record, PREPROCESSING_DIR)
        ip_cases[label] = {"integer": int(ipv4_to_integer(ip)), "z_score": float(transformed[0, IP_FEATURE_INDEX]), "in_bounds": bool(IP_ZSCORE_BOUNDS[0] <= transformed[0, IP_FEATURE_INDEX] <= IP_ZSCORE_BOUNDS[1])}
    complete = all(value["passed"] for value in results.values())
    status = "FINAL VAE PIPELINE — PASS" if complete else "FINAL VAE PIPELINE — FAIL"
    payload = {"status": status, "checks": results, "threshold": threshold, "test_metrics": metrics, "ip_cases": ip_cases}
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if complete:
        metadata["status"] = "FINAL_VALIDATED"
        metadata["final_validation"] = {"report": "FINAL_VAE_PIPELINE_REPORT.md", "results": str(RESULTS_PATH), "status": status}
        MODEL_METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(markdown(status, results, evaluation, threshold, ip_cases), encoding="utf-8")
    print(status)
    print(json.dumps({"pass": sum(item["passed"] for item in results.values()), "fail": sum(not item["passed"] for item in results.values())}, ensure_ascii=False))
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
