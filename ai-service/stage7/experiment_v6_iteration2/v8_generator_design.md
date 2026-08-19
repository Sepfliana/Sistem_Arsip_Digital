# V8 Anomaly Dataset Design

## Problem
V7 anomalies overlap with localhost in MSE space:
- anomaly P25 (0.25) ≈ localhost median (0.24)
- No threshold satisfies both FPR<=5% and recall>=70%

## Root Cause
V6 anomalies only mutate 2-4 features. The VAE compensates via the 5-7 unchanged features.
The `status` feature (81.5% of localhost MSE) is NEVER mutated in V6.

## V8 Design Principles
1. Mutate 6+ features simultaneously (including status)
2. Create conflicting signals (behaviorally inconsistent)
3. Ensure anomaly MSE >> localhost P95 (0.29)
4. Each anomaly must be jointly rare (<=0.1%)

## Anomaly Types (1000 total)

### Type 1: impossible_credential_shift (334)
- **Conflicting signals:** Success + impossible context
- Mutated: user_id, status, ip_address, device, hour, duration_ms
- Key: status="Berhasil" but IP External + VM + Night + ZeroDuration
- User ID: 9000-9999 (out of training range 1-86)

### Type 2: admin_breach_compound (333)
- **Conflicting signals:** Failed admin action from external at night
- Mutated: status, aksi, ip_address, device, hour, object_count, user_id
- Key: status="Gagal" + admin action + IP External + VM + Night + HighObj(50-200)

### Type 3: silent_data_exfiltration (333)
- **Conflicting signals:** Zero duration + massive data + external
- Mutated: status, ip_address, device, hour, duration_ms, object_count, user_id
- Key: status="UNKNOWN" + IP External + ZeroDuration + VeryHighObj(100-500)

## Expected MSE Separation

| Feature | V6 Anomaly MSE | V8 Expected MSE | Localhost P95 |
|---------|---------------|-----------------|---------------|
| status | 0.098 | **HIGH** (UNKNOWN/Gagal) | 18.026 |
| ip_address | ~0 | **1.0** (External) | 0.988 |
| device | 3.042 | **3.0** (VM) | 0.092 |
| hour | 2.485 | **2.5** (Night) | 1.045 |
| duration_ms | ~0 | **1.0** (Zero) | 1.002 |
| object_count | 0.117 | **HIGH** (50-500) | 0.488 |
| user_id | 0.044 | **0.5** (9000+) | 0.128 |

**Total expected MSE:** V8 anomalies should have significantly higher MSE than localhost P95 (0.29).

## Validation Criteria
- All records mutated >= 6 features
- All records have conflicting signals
- Object count: Type2 >= 50, Type3 >= 100
- All records have External IP
- All records have Night hour (0-5)

## Output Files
- v8_anomaly_raw.csv (1000 records)
- v8_validation_summary.csv
- v8_generator_design.md

## Seed
SEED = 42 (deterministic generation)
