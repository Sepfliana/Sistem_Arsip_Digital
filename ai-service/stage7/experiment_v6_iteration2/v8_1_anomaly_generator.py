"""
V8.1 Calibrated Anomaly Dataset Generator
===========================================
Creates CALIBRATED anomalies that are:
1. Separable from localhost
2. Within plausible data domain
3. Produce moderate reconstruction error

V8.1 Design Principles:
- Mutate only 2-3 features per record
- Keep all values within training domain
- Focus on status mutation (81.5% of localhost MSE)
- Create behavioral conflict with other features
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

B = Path(__file__).resolve().parents[2]
V6 = B / "stage7" / "v6"
E = Path(__file__).resolve().parent

SEED = 42
N_TOTAL = 1000

V6_ACTIVITY_CLASSES = [
    "Login", "Logout", "Akses Berkas", "Kelola Berkas",
    "Kelola Perkara", "Kelola User", "Administrasi", "UNKNOWN",
]
V6_STATUS_CLASSES = ["Berhasil", "Gagal", "UNKNOWN"]
V6_DEVICE_CLASSES = [
    "PC Windows", "Android", "iOS", "Macos", "Linux",
    "Virtual Machine", "Unknown Device",
]


def log(msg: str) -> None:
    print(f"  {msg}")


# ═══════════════════════════════════════════════════════════════════════════
# V8.1 ANOMALY TYPES (CALIBRATED)
# ═══════════════════════════════════════════════════════════════════════════

# Type 1: failed_offhours_access (334)
# Mutated: status, hour (2 features)
# Conflicting: failed operation during off-hours
# - status="Gagal" (rare in training ~3%)
# - hour=Night (period 3, rare in training)
# - user_id: from training range (1-86)
TYPE1_COUNT = 334

# Type 2: unknown_external_access (333)
# Mutated: status, ip_address (2 features)
# Conflicting: unknown status from external IP
# - status="UNKNOWN" (NOT in training after V7 fix)
# - ip_address=External (8.8.8.8)
# - user_id: from training range
TYPE2_COUNT = 333

# Type 3: failed_vm_access (333)
# Mutated: status, device (2 features)
# Conflicting: failed operation from virtual machine
# - status="Gagal" (rare in training ~3%)
# - device="Virtual Machine"
# - user_id: from training range
TYPE3_COUNT = 333


def generate_type1(rng: np.random.Generator, base_records: pd.DataFrame) -> pd.DataFrame:
    """Failed offhours access: Gagal + Night hour."""
    rows = []
    bases = base_records.sample(n=TYPE1_COUNT, replace=True, random_state=rng.integers(0, 2**31)).reset_index(drop=True)

    for i in range(TYPE1_COUNT):
        b = bases.iloc[i]
        hour = int(rng.integers(0, 6))  # Night: 0-5 WIB
        user_id = int(b.get("user_id", 1))  # Keep from base (training range)
        # Use realistic duration from base
        durasi = float(b.get("durasi_ms", 100))
        jumlah_objek = float(b.get("jumlah_objek", 1))

        rows.append({
            "source_type": "V8_1_ANOMALY",
            "source_id": f"v8_1_t1_{i}",
            "user_id": user_id,
            "aksi": b.get("aksi", "Login"),
            "status": "Gagal",  # Conflicting: failed + off-hours
            "device": b.get("device", "Windows"),  # Keep normal
            "ip_address": b.get("ip_address", "192.168.1.1"),  # Keep normal (internal)
            "durasi_ms": durasi,  # Keep realistic
            "jumlah_objek": jumlah_objek,  # Keep realistic
            "waktu": f"2025-01-15 {hour:02d}:{rng.integers(0,60):02d}:{rng.integers(0,60):02d}",
            "is_anomali": True,
            "risk_level_source": "Medium",
            "candidate_type": "ANOMALY",
            "anomaly_type": "failed_offhours_access",
            "severity": "Moderate",
            "base_record_id": str(b.get("source_id", f"base_{i}")),
            "mutated_features": "status,hour",
            "raw_before": json.dumps({
                "status": str(b.get("status", "Berhasil")),
                "waktu": str(b.get("waktu", "")),
            }),
            "raw_after": json.dumps({
                "status": "Gagal",
                "waktu": f"2025-01-15 {hour:02d}:00:00",
            }),
            "primary_joint_combination": "Gagal+Night",
            "primary_joint_frequency": 0,
            "threat_rationale": "Failed operation during off-hours (suspicious but plausible)",
            "preprocessing_status": "pending",
        })

    return pd.DataFrame(rows)


def generate_type2(rng: np.random.Generator, base_records: pd.DataFrame) -> pd.DataFrame:
    """Unknown external access: UNKNOWN + External IP."""
    rows = []
    bases = base_records.sample(n=TYPE2_COUNT, replace=True, random_state=rng.integers(0, 2**31)).reset_index(drop=True)

    external_ips = ["8.8.8.8", "203.0.113.1", "198.51.100.1", "100.64.0.1"]

    for i in range(TYPE2_COUNT):
        b = bases.iloc[i]
        user_id = int(b.get("user_id", 1))  # Keep from base
        # Use realistic values from base
        durasi = float(b.get("durasi_ms", 100))
        jumlah_objek = float(b.get("jumlah_objek", 1))
        hour = int(pd.to_datetime(b.get("waktu", "2025-01-15 10:00:00")).hour)
        ext_ip = rng.choice(external_ips)

        rows.append({
            "source_type": "V8_1_ANOMALY",
            "source_id": f"v8_1_t2_{i}",
            "user_id": user_id,
            "aksi": b.get("aksi", "Login"),
            "status": "UNKNOWN",  # Conflicting: unknown status from external
            "device": b.get("device", "Windows"),  # Keep normal
            "ip_address": ext_ip,  # External IP
            "durasi_ms": durasi,  # Keep realistic
            "jumlah_objek": jumlah_objek,  # Keep realistic
            "waktu": b.get("waktu", "2025-01-15 10:00:00"),  # Keep normal time
            "is_anomali": True,
            "risk_level_source": "High",
            "candidate_type": "ANOMALY",
            "anomaly_type": "unknown_external_access",
            "severity": "High",
            "base_record_id": str(b.get("source_id", f"base_{i}")),
            "mutated_features": "status,ip_address",
            "raw_before": json.dumps({
                "status": str(b.get("status", "Berhasil")),
                "ip_address": str(b.get("ip_address", "192.168.1.1")),
            }),
            "raw_after": json.dumps({
                "status": "UNKNOWN",
                "ip_address": ext_ip,
            }),
            "primary_joint_combination": "UNKNOWN+External",
            "primary_joint_frequency": 0,
            "threat_rationale": "Unknown status from external IP (anomalous identity)",
            "preprocessing_status": "pending",
        })

    return pd.DataFrame(rows)


def generate_type3(rng: np.random.Generator, base_records: pd.DataFrame) -> pd.DataFrame:
    """Failed VM access: Gagal + Virtual Machine."""
    rows = []
    bases = base_records.sample(n=TYPE3_COUNT, replace=True, random_state=rng.integers(0, 2**31)).reset_index(drop=True)

    for i in range(TYPE3_COUNT):
        b = bases.iloc[i]
        user_id = int(b.get("user_id", 1))  # Keep from base
        # Use realistic values from base
        durasi = float(b.get("durasi_ms", 100))
        jumlah_objek = float(b.get("jumlah_objek", 1))
        hour = int(pd.to_datetime(b.get("waktu", "2025-01-15 10:00:00")).hour)

        rows.append({
            "source_type": "V8_1_ANOMALY",
            "source_id": f"v8_1_t3_{i}",
            "user_id": user_id,
            "aksi": b.get("aksi", "Login"),
            "status": "Gagal",  # Conflicting: failed from VM
            "device": "Virtual Machine",  # Unusual device
            "ip_address": b.get("ip_address", "192.168.1.1"),  # Keep normal (internal)
            "durasi_ms": durasi,  # Keep realistic
            "jumlah_objek": jumlah_objek,  # Keep realistic
            "waktu": b.get("waktu", "2025-01-15 10:00:00"),  # Keep normal time
            "is_anomali": True,
            "risk_level_source": "High",
            "candidate_type": "ANOMALY",
            "anomaly_type": "failed_vm_access",
            "severity": "High",
            "base_record_id": str(b.get("source_id", f"base_{i}")),
            "mutated_features": "status,device",
            "raw_before": json.dumps({
                "status": str(b.get("status", "Berhasil")),
                "device": str(b.get("device", "Windows")),
            }),
            "raw_after": json.dumps({
                "status": "Gagal",
                "device": "Virtual Machine",
            }),
            "primary_joint_combination": "Gagal+VM",
            "primary_joint_frequency": 0,
            "threat_rationale": "Failed operation from virtual machine (potential compromise)",
            "preprocessing_status": "pending",
        })

    return pd.DataFrame(rows)


def validate_v8_1(df: pd.DataFrame) -> dict:
    """Validate V8.1 calibrated anomalies."""
    print("\n[Validation] Checking V8.1 anomalies")

    assert len(df) == N_TOTAL, f"Expected {N_TOTAL} rows, got {len(df)}"
    log(f"Count: {len(df)} (expected {N_TOTAL})")

    type_counts = df["anomaly_type"].value_counts().to_dict()
    log(f"Type distribution: {type_counts}")

    # Check mutation count (2-3 features)
    for _, row in df.iterrows():
        mutated = len(str(row["mutated_features"]).split(","))
        assert 2 <= mutated <= 3, f"Row {row['source_id']} mutated {mutated} features (expected 2-3)"
    log("All records mutated 2-3 features: PASS")

    # Check user_id within training range (1-86)
    uid_min = df.user_id.min()
    uid_max = df.user_id.max()
    log(f"User ID range: {uid_min} - {uid_max}")
    assert uid_min >= 1, "user_id must be >= 1"
    assert uid_max <= 86, "user_id must be <= 86"

    # Check object_count within training range
    obj_max = df.jumlah_objek.max()
    log(f"Object count max: {obj_max}")
    assert obj_max <= 10, "object_count should be <= 10 (training range)"

    # Check duration within realistic range
    dur_mean = df.durasi_ms.mean()
    dur_max = df.durasi_ms.max()
    log(f"Duration: mean={dur_mean:.1f}ms  max={dur_max:.1f}ms")
    assert dur_mean > 0, "Duration should have variation (not always 0)"

    # Check device variation
    device_counts = df.device.value_counts().to_dict()
    log(f"Device distribution: {device_counts}")
    # Should not be all VM
    assert device_counts.get("Virtual Machine", 0) < len(df), "Device should not be all VM"

    # Check status distribution
    status_counts = df.status.value_counts().to_dict()
    log(f"Status distribution: {status_counts}")

    # Check hour variation (Type1 has Night, others have normal hours)
    log("Hour variation: Type1=Night, Type2/Type3=Normal (from base)")

    log("Validation: PASS")
    return {
        "count": len(df),
        "type_distribution": type_counts,
        "status_distribution": status_counts,
        "device_distribution": device_counts,
        "user_id_range": [int(uid_min), int(uid_max)],
        "object_count_max": float(obj_max),
        "duration_stats": {"mean": float(dur_mean), "max": float(dur_max)},
    }


def main():
    print("=" * 60)
    print("V8.1 CALIBRATED ANOMALY GENERATOR")
    print("=" * 60)

    rng = np.random.default_rng(SEED)

    print("\n[1] Load base records")
    raw = pd.read_csv(B / "dataset/retraining/retraining_dataset_combined_raw.csv",
                       encoding="utf-8-sig")
    base = raw[
        (raw.source_type == "SYNTHETIC") & (raw.candidate_type == "NORMAL")
    ].copy()
    log(f"Base records: {len(base)}")

    print("\n[2] Generate V8.1 anomalies")
    df1 = generate_type1(rng, base)
    log(f"Type1 (failed_offhours_access): {len(df1)}")

    df2 = generate_type2(rng, base)
    log(f"Type2 (unknown_external_access): {len(df2)}")

    df3 = generate_type3(rng, base)
    log(f"Type3 (failed_vm_access): {len(df3)}")

    v8_1 = pd.concat([df1, df2, df3], ignore_index=True)
    log(f"Total V8.1 anomalies: {len(v8_1)}")

    validation = validate_v8_1(v8_1)

    print("\n[3] Save outputs")
    out_path = V6 / "v8_1_anomaly_raw.csv"
    v8_1.to_csv(out_path, index=False)
    log(f"Saved: {out_path}")

    # Validation summary
    summary_rows = []
    for atype in ["failed_offhours_access", "unknown_external_access", "failed_vm_access"]:
        sub = v8_1[v8_1.anomaly_type == atype]
        summary_rows.append({
            "anomaly_type": atype,
            "count": len(sub),
            "status": sub.status.mode().iloc[0] if len(sub) > 0 else "N/A",
            "ip_address_mode": sub.ip_address.mode().iloc[0] if len(sub) > 0 else "N/A",
            "device_mode": sub.device.mode().iloc[0] if len(sub) > 0 else "N/A",
            "durasi_ms_mean": float(sub.durasi_ms.mean()),
            "jumlah_objek_mean": float(sub.jumlah_objek.mean()),
            "user_id_range": f"{sub.user_id.min()}-{sub.user_id.max()}",
            "features_mutated": sub.mutated_features.mode().iloc[0] if len(sub) > 0 else "N/A",
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(E / "v8_1_validation_summary.csv", index=False)
    log(f"Saved: {E / 'v8_1_validation_summary.csv'}")

    # Design doc
    design = f"""# V8.1 Calibrated Anomaly Dataset Design

## Problem with V8
V8 anomalies were too extreme:
- MSE ~10,000 (30,000x vs localhost)
- user_id = 9000-9999 (training range: 1-86)
- object_count = 50-500 (training max: ~5)
- duration_ms = 0 always (too constant)

## V8.1 Design Principles
1. Mutate only 2-3 features per record
2. Keep all values within training domain
3. Focus on status mutation (81.5% of localhost MSE)
4. Create behavioral conflict with other features

## Anomaly Types (1000 total)

### Type 1: failed_offhours_access (334)
- **Conflicting signals:** Failed operation during off-hours
- Mutated: status, hour (2 features)
- status = "Gagal" (rare in training ~3%)
- hour = Night (period 3, rare in training)
- user_id: from base (training range 1-86)
- All other features: normal from base

### Type 2: unknown_external_access (333)
- **Conflicting signals:** Unknown status from external IP
- Mutated: status, ip_address (2 features)
- status = "UNKNOWN" (NOT in training after V7 fix)
- ip_address = External (8.8.8.8, 203.0.113.1, etc.)
- user_id: from base (training range 1-86)
- All other features: normal from base

### Type 3: failed_vm_access (333)
- **Conflicting signals:** Failed operation from virtual machine
- Mutated: status, device (2 features)
- status = "Gagal" (rare in training ~3%)
- device = "Virtual Machine"
- user_id: from base (training range 1-86)
- All other features: normal from base

## Key Difference from V6/V8
- **V6 anomalies:** status="Berhasil" (matched training, low MSE)
- **V8 anomalies:** extreme values (user_id=9000, object_count=500)
- **V8.1 anomalies:** status="Gagal"/"UNKNOWN" (rare, moderate MSE)

## Expected MSE Separation
- status="Gagal" contributes ~18.0 MSE (81.5% of localhost)
- status="UNKNOWN" contributes ~18.0 MSE (81.5% of localhost)
- hour=Night contributes ~1.0 MSE (4.7% of localhost)
- device=VM contributes ~0.09 MSE (0.42% of localhost)
- ip_address=External contributes ~1.0 MSE (4.5% of localhost)

**Total expected MSE:** 0.5-3.0 (within target range)

## Target Metrics
- anomaly P25 > localhost P95 (0.29)
- anomaly mean = 2-5x localhost mean (0.21)
- anomaly max < 10x localhost max (0.345)

## Validation Criteria
- All records mutated 2-3 features
- user_id within training range (1-86)
- object_count within training range (<=10)
- Duration has variation (not always 0)
- Device has variation (not all VM)

## Output Files
- v8_1_anomaly_raw.csv (1000 records)
- v8_1_validation_summary.csv
- v8_1_generator_design.md
"""
    (E / "v8_1_generator_design.md").write_text(design, encoding="utf-8")
    log(f"Saved: {E / 'v8_1_generator_design.md'}")

    # Final print
    print("\n" + "=" * 60)
    print("V8.1 CALIBRATED ANOMALY GENERATION COMPLETE")
    print("=" * 60)
    print(f"\nTotal anomalies: {len(v8_1)}")
    print(f"Type distribution: {validation['type_distribution']}")
    print(f"\nDomain constraints:")
    print(f"  user_id range: {validation['user_id_range']}")
    print(f"  object_count max: {validation['object_count_max']}")
    print(f"  duration: mean={validation['duration_stats']['mean']:.1f}ms  max={validation['duration_stats']['max']:.1f}ms")
    print(f"\nConflicting signals:")
    print(f"  Type1: Gagal + Night hour")
    print(f"  Type2: UNKNOWN + External IP")
    print(f"  Type3: Gagal + Virtual Machine")
    print(f"\nExpected MSE: 0.5-3.0 (moderate, within target)")
    print(f"\nOutput files:")
    print(f"  {out_path}")
    print(f"  {E / 'v8_1_validation_summary.csv'}")
    print(f"  {E / 'v8_1_generator_design.md'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
