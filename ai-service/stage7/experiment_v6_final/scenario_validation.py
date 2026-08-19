"""
Stage 8 FINAL — Scenario Validation
=====================================
Read-only validation of model behavior on real-world scenarios.
No retraining. No modification. Pure inference evaluation.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

# ── Paths ───────────────────────────────────────────────────────────────────
B = Path(__file__).resolve().parents[2]   # ai-service/
E = Path(__file__).resolve().parent       # experiment_v6_final/
O = E

# ── Import inference pipeline ──────────────────────────────────────────────
sys.path.insert(0, str(B / "stage7" / "final_artifacts"))
from inference_pipeline import AnomalyDetector, VariationalAutoencoder

THRESHOLD = 0.296394
MONITORED_LOW = THRESHOLD * 0.80   # 0.237115
MONITORED_HIGH = THRESHOLD         # 0.296394

# ── Scenario Definitions ───────────────────────────────────────────────────
SCENARIOS = [
    # ── NORMAL ──
    {
        "name": "N1: Login 10:00 internal PC",
        "category": "NORMAL",
        "expected_mse": "low",
        "expected_class": "NORMAL",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "192.168.1.100",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T10:00:00+07:00",
        },
    },
    {
        "name": "N2: File access 14:00 internal",
        "category": "NORMAL",
        "expected_mse": "low",
        "expected_class": "NORMAL",
        "record": {
            "user_id": 5, "aksi": "Akses Berkas", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "192.168.1.50",
            "durasi_ms": 5000, "jumlah_objek": 2,
            "waktu": "2026-08-19T14:00:00+07:00",
        },
    },
    {
        "name": "N3: Logout 17:30 internal",
        "category": "NORMAL",
        "expected_mse": "low",
        "expected_class": "NORMAL",
        "record": {
            "user_id": 3, "aksi": "Logout", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "192.168.1.100",
            "durasi_ms": 800, "jumlah_objek": 0,
            "waktu": "2026-08-19T17:30:00+07:00",
        },
    },
    {
        "name": "N4: Kelola Perkara 09:00 internal",
        "category": "NORMAL",
        "expected_mse": "low",
        "expected_class": "NORMAL",
        "record": {
            "user_id": 10, "aksi": "Kelola Perkara", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "192.168.1.200",
            "durasi_ms": 8000, "jumlah_objek": 3,
            "waktu": "2026-08-19T09:00:00+07:00",
        },
    },
    # ── MONITORED ──
    {
        "name": "M1: Login 02:00 (night)",
        "category": "MONITORED",
        "expected_mse": "medium",
        "expected_class": "MONITORED",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "192.168.1.100",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T02:00:00+07:00",
        },
    },
    {
        "name": "M2: Weekend login 11:00",
        "category": "MONITORED",
        "expected_mse": "medium",
        "expected_class": "MONITORED",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "192.168.1.100",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-22T11:00:00+07:00",
        },
    },
    {
        "name": "M3: External IP login",
        "category": "MONITORED",
        "expected_mse": "medium",
        "expected_class": "MONITORED",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "8.8.8.8",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T10:00:00+07:00",
        },
    },
    {
        "name": "M4: Android device access",
        "category": "MONITORED",
        "expected_mse": "medium",
        "expected_class": "MONITORED",
        "record": {
            "user_id": 1, "aksi": "Akses Berkas", "status": "Berhasil",
            "device": "Android", "ip_address": "192.168.1.100",
            "durasi_ms": 3000, "jumlah_objek": 1,
            "waktu": "2026-08-19T14:00:00+07:00",
        },
    },
    {
        "name": "M5: Virtual Machine login",
        "category": "MONITORED",
        "expected_mse": "medium",
        "expected_class": "MONITORED",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "Virtual Machine", "ip_address": "192.168.1.100",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T10:00:00+07:00",
        },
    },
    {
        "name": "M6: Gagal status work hours",
        "category": "MONITORED",
        "expected_mse": "medium",
        "expected_class": "MONITORED",
        "record": {
            "user_id": 5, "aksi": "Kelola Berkas", "status": "Gagal",
            "device": "PC Windows", "ip_address": "192.168.1.50",
            "durasi_ms": 1200, "jumlah_objek": 1,
            "waktu": "2026-08-19T14:00:00+07:00",
        },
    },
    # ── BORDERLINE ──
    {
        "name": "B1: Night + external IP",
        "category": "BORDERLINE",
        "expected_mse": "medium-high",
        "expected_class": "BORDERLINE",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "PC Windows", "ip_address": "203.0.113.1",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T03:00:00+07:00",
        },
    },
    {
        "name": "B2: Unknown status + internal",
        "category": "BORDERLINE",
        "expected_mse": "medium-high",
        "expected_class": "BORDERLINE",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "UNKNOWN",
            "device": "PC Windows", "ip_address": "192.168.1.100",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T10:00:00+07:00",
        },
    },
    {
        "name": "B3: VM + external IP",
        "category": "BORDERLINE",
        "expected_mse": "medium-high",
        "expected_class": "BORDERLINE",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Berhasil",
            "device": "Virtual Machine", "ip_address": "8.8.8.8",
            "durasi_ms": 2500, "jumlah_objek": 1,
            "waktu": "2026-08-19T10:00:00+07:00",
        },
    },
    {
        "name": "B4: Gagal + night + internal",
        "category": "BORDERLINE",
        "expected_mse": "medium-high",
        "expected_class": "BORDERLINE",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Gagal",
            "device": "PC Windows", "ip_address": "192.168.1.100",
            "durasi_ms": 0, "jumlah_objek": 1,
            "waktu": "2026-08-19T02:00:00+07:00",
        },
    },
    # ── ANOMALY ──
    {
        "name": "A1: Gagal + external + VM",
        "category": "ANOMALY",
        "expected_mse": "high",
        "expected_class": "ANOMALY",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "Gagal",
            "device": "Virtual Machine", "ip_address": "8.8.8.8",
            "durasi_ms": 0, "jumlah_objek": 1,
            "waktu": "2026-08-19T14:00:00+07:00",
        },
    },
    {
        "name": "A2: Unknown + night + external",
        "category": "ANOMALY",
        "expected_mse": "high",
        "expected_class": "ANOMALY",
        "record": {
            "user_id": 1, "aksi": "Login", "status": "UNKNOWN",
            "device": "PC Windows", "ip_address": "8.8.8.8",
            "durasi_ms": 0, "jumlah_objek": 1,
            "waktu": "2026-08-19T03:00:00+07:00",
        },
    },
    {
        "name": "A3: Admin 03:00 external VM Gagal",
        "category": "ANOMALY",
        "expected_mse": "high",
        "expected_class": "ANOMALY",
        "record": {
            "user_id": 1, "aksi": "Kelola User", "status": "Gagal",
            "device": "Virtual Machine", "ip_address": "203.0.113.1",
            "durasi_ms": 0, "jumlah_objek": 5,
            "waktu": "2026-08-19T03:00:00+07:00",
        },
    },
    {
        "name": "A4: Gagal + night + external + VM",
        "category": "ANOMALY",
        "expected_mse": "high",
        "expected_class": "ANOMALY",
        "record": {
            "user_id": 1, "aksi": "Kelola Berkas", "status": "Gagal",
            "device": "Virtual Machine", "ip_address": "8.8.8.8",
            "durasi_ms": 0, "jumlah_objek": 10,
            "waktu": "2026-08-19T01:00:00+07:00",
        },
    },
    {
        "name": "A5: Unknown + weekend + external",
        "category": "ANOMALY",
        "expected_mse": "high",
        "expected_class": "ANOMALY",
        "record": {
            "user_id": 1, "aksi": "Kelola Perkara", "status": "UNKNOWN",
            "device": "PC Windows", "ip_address": "203.0.113.1",
            "durasi_ms": 0, "jumlah_objek": 3,
            "waktu": "2026-08-22T02:00:00+07:00",
        },
    },
]


def classify(mse: float) -> str:
    if mse >= THRESHOLD:
        return "ANOMALY"
    elif mse >= MONITORED_LOW:
        return "MONITORED"
    else:
        return "NORMAL"


def match_ok(predicted: str, expected_cat: str) -> bool:
    """Check if predicted class matches expected category group."""
    if expected_cat == "NORMAL":
        return predicted == "NORMAL"
    elif expected_cat == "MONITORED":
        return predicted in ("NORMAL", "MONITORED")
    elif expected_cat == "BORDERLINE":
        return predicted in ("MONITORED", "ANOMALY")
    elif expected_cat == "ANOMALY":
        return predicted in ("MONITORED", "ANOMALY")
    return False


def main():
    print("=" * 65)
    print("STAGE 8 FINAL — SCENARIO VALIDATION")
    print("=" * 65)

    # ── Load model ──────────────────────────────────────────────────────────
    print("\n[1] Loading model and inference pipeline...")
    detector = AnomalyDetector()
    print(f"    Threshold: {THRESHOLD}")
    print(f"    MONITORED band: [{MONITORED_LOW:.6f}, {MONITORED_HIGH:.6f})")
    print(f"    Scenarios loaded: {len(SCENARIOS)}")

    # ── Run inference ───────────────────────────────────────────────────────
    print("\n[2] Running inference on all scenarios...\n")

    results = []
    for sc in SCENARIOS:
        result = detector.predict(sc["record"])
        mse = result["mse"]
        predicted = classify(mse)
        matched = match_ok(predicted, sc["category"])
        results.append({
            "name": sc["name"],
            "category": sc["category"],
            "mse": round(mse, 6),
            "predicted": predicted,
            "expected_class": sc["expected_class"],
            "match": "YES" if matched else "NO",
        })

    # ── Print table ─────────────────────────────────────────────────────────
    hdr = f"{'Scenario':<42} {'MSE':>8} {'Predicted':<10} {'Expected':<10} {'Match':<4}"
    print(hdr)
    print("-" * 82)
    for r in results:
        mse_str = f"{r['mse']:.6f}"
        print(f"{r['name']:<42} {mse_str:>8} {r['predicted']:<10} {r['expected_class']:<10} {r['match']:<4}")

    # ── Summary metrics ─────────────────────────────────────────────────────
    total = len(results)
    correct = sum(1 for r in results if r["match"] == "YES")
    accuracy = correct / total * 100

    # False positives: NORMAL category predicted as ANOMALY
    fp = sum(1 for r in results if r["category"] == "NORMAL" and r["predicted"] == "ANOMALY")
    # False negatives: ANOMALY category predicted as NORMAL
    fn = sum(1 for r in results if r["category"] == "ANOMALY" and r["predicted"] == "NORMAL")

    # Per-category accuracy
    cat_stats = {}
    for cat in ["NORMAL", "MONITORED", "BORDERLINE", "ANOMALY"]:
        cat_results = [r for r in results if r["category"] == cat]
        cat_correct = sum(1 for r in cat_results if r["match"] == "YES")
        cat_total = len(cat_results)
        cat_stats[cat] = {
            "total": cat_total,
            "correct": cat_correct,
            "accuracy": round(cat_correct / cat_total * 100, 1) if cat_total > 0 else 0,
        }

    # MSE stats per category
    cat_mse = {}
    for cat in ["NORMAL", "MONITORED", "BORDERLINE", "ANOMALY"]:
        cat_mse_vals = [r["mse"] for r in results if r["category"] == cat]
        if cat_mse_vals:
            cat_mse[cat] = {
                "min": round(min(cat_mse_vals), 6),
                "max": round(max(cat_mse_vals), 6),
                "mean": round(sum(cat_mse_vals) / len(cat_mse_vals), 6),
            }

    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"\nTotal scenarios:  {total}")
    print(f"Correct:          {correct}/{total}")
    print(f"Accuracy:         {accuracy:.1f}%")
    print(f"False Positives:  {fp} (NORMAL -> ANOMALY)")
    print(f"False Negatives:  {fn} (ANOMALY -> NORMAL)")

    print("\nPer-Category Breakdown:")
    for cat, s in cat_stats.items():
        mse_info = cat_mse.get(cat, {})
        mse_range = f"MSE [{mse_info.get('min', 0):.6f} — {mse_info.get('max', 0):.6f}]" if mse_info else ""
        print(f"  {cat:<12} {s['correct']}/{s['total']} correct ({s['accuracy']:.1f}%)  {mse_range}")

    print("\nMSE Distribution:")
    for cat in ["NORMAL", "MONITORED", "BORDERLINE", "ANOMALY"]:
        if cat in cat_mse:
            m = cat_mse[cat]
            print(f"  {cat:<12} min={m['min']:.6f}  mean={m['mean']:.6f}  max={m['max']:.6f}")

    # ── Classification boundary analysis ────────────────────────────────────
    print("\nClassification Boundaries:")
    print(f"  NORMAL     : MSE < {MONITORED_LOW:.6f}")
    print(f"  MONITORED  : {MONITORED_LOW:.6f} <= MSE < {MONITORED_HIGH:.6f}")
    print(f"  ANOMALY    : MSE >= {MONITORED_HIGH:.6f}")

    # Find closest scenario to threshold
    closest = min(results, key=lambda r: abs(r["mse"] - THRESHOLD))
    print(f"\n  Closest to threshold: {closest['name']}")
    print(f"    MSE: {closest['mse']:.6f} (delta: {abs(closest['mse'] - THRESHOLD):.6f})")

    # ── Final verdict ───────────────────────────────────────────────────────
    verdict = "ACCEPTABLE" if accuracy >= 85 and fp == 0 and fn == 0 else "NEEDS REVIEW"
    print(f"\n{'=' * 65}")
    print("SCENARIO VALIDATION RESULT")
    print(f"{'=' * 65}")
    print(f"Accuracy: {accuracy:.1f}%")
    print(f"False Positive: {fp}")
    print(f"False Negative: {fn}")
    print(f"\nConclusion:")
    print(f"MODEL BEHAVIOR: {verdict}")
    print(f"{'=' * 65}")

    # ── Save CSV ────────────────────────────────────────────────────────────
    csv_path = O / "scenario_validation_results.csv"
    df_out = pd.DataFrame(results)
    df_out.to_csv(csv_path, index=False)
    print(f"\nSaved: {csv_path}")

    # ── Save detailed JSON ──────────────────────────────────────────────────
    summary = {
        "threshold": THRESHOLD,
        "monitored_low": MONITORED_LOW,
        "monitored_high": MONITORED_HIGH,
        "total": total,
        "correct": correct,
        "accuracy_pct": round(accuracy, 1),
        "false_positives": fp,
        "false_negatives": fn,
        "verdict": verdict,
        "per_category": cat_stats,
        "mse_distribution": cat_mse,
        "results": results,
    }
    json_path = O / "scenario_validation_summary.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved: {json_path}")


if __name__ == "__main__":
    main()
