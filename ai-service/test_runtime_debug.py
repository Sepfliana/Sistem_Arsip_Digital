"""Debug script to test runtime preprocessing + scoring for a LOGIN_SUCCESS event."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.final_preprocessing_contract import (
    preprocess_for_inference, _normalize_activity, _normalize_status, _normalize_device,
    FEATURE_COLUMNS, load_final_artifacts, records_to_unscaled_matrix, scale_matrix,
)
from services.final_vae_pipeline import (
    load_final_model, load_final_threshold, reconstruction_details,
    build_explanation, risk_level,
)


def test_login(aksi, status, device, user_id, ip, durasi_ms, objek, waktu):
    record = {
        "waktu": waktu,
        "user_id": user_id,
        "aksi": aksi,
        "status": status,
        "device": device,
        "ip_address": ip,
        "durasi_ms": durasi_ms,
        "jumlah_objek": objek,
    }

    print("=" * 70)
    print(f"INPUT: aksi={aksi} status={status} user_id={user_id} ip={ip} waktu={waktu}")
    print(f"       device={device[:60]}...")
    print()

    norm_act = _normalize_activity(aksi)
    norm_stat = _normalize_status(status)
    norm_dev = _normalize_device(device)
    print(f"NORMALIZED: activity={norm_act} status={norm_stat} device={norm_dev}")

    artifact_dir = Path("dataset/final_stage1_ssot/preprocessing_stage2")
    encoder, scaler = load_final_artifacts(artifact_dir)
    unscaled = records_to_unscaled_matrix([record], encoder)
    print(f"\nUNSCALED (9 features):")
    for name, val in zip(FEATURE_COLUMNS, unscaled[0]):
        print(f"  {name:15s} = {val:.4f}")

    scaled = scale_matrix(unscaled, scaler)
    print(f"\nSCALED + CLIPPED:")
    for name, val in zip(FEATURE_COLUMNS, scaled[0]):
        print(f"  {name:15s} = {val:.6f}")

    preprocessed = preprocess_for_inference(record, artifact_dir)
    print(f"\nPREPROCESSED SHAPE: {preprocessed.shape}")

    model = load_final_model()
    threshold = load_final_threshold()
    details = reconstruction_details(preprocessed)
    score = float(details["anomaly_scores"][0])
    rl = risk_level(score, threshold)
    errors, contributions, dominant = build_explanation(details["feature_errors"][0])

    print(f"\nSCORE:       {score:.6f}")
    print(f"THRESHOLD:   {threshold:.6f}")
    print(f"RISK LEVEL:  {rl}")
    print(f"IS ANOMALY:  {score > threshold}")
    print(f"\nFEATURE ERRORS:")
    for name in FEATURE_COLUMNS:
        print(f"  {name:15s} = {errors[name]:.6f}  ({contributions[name]*100:.1f}%)")
    print(f"\nDOMINANT: {dominant[0]['feature']} ({dominant[0]['contribution']*100:.1f}%)")
    print("=" * 70)
    print()
    return score


if __name__ == "__main__":
    windows_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    print("\n>>> TEST 1: LOGIN_SUCCESS + SUCCESS + Windows + jam 17 (kerja)")
    test_login("LOGIN_SUCCESS", "SUCCESS", windows_ua, 1, "192.168.1.10", 120, 1, "2026-08-25T17:24:00")

    print("\n>>> TEST 2: LOGIN_SUCCESS + SUCCESS + Windows + jam 10 (kerja)")
    test_login("LOGIN_SUCCESS", "SUCCESS", windows_ua, 1, "192.168.1.10", 120, 1, "2026-08-25T10:00:00")

    print("\n>>> TEST 3: LOGIN_SUCCESS + SUCCESS + Windows + jam 23 (malam)")
    test_login("LOGIN_SUCCESS", "SUCCESS", windows_ua, 1, "192.168.1.10", 120, 1, "2026-08-25T23:00:00")

    print("\n>>> TEST 4: LOGOUT + SUCCESS + Windows + jam 16")
    test_login("LOGOUT", "SUCCESS", windows_ua, 1, "192.168.1.10", 80, 1, "2026-08-25T16:37:00")
