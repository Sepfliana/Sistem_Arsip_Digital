# V8.1 Calibrated Anomaly Dataset Design

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
