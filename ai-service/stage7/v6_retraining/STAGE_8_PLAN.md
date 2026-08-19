# Stage 8 — Controlled Retraining with V6 Preprocessing Pipeline

**Date:** 2026-08-18
**Status:** PLAN (read-only)
**Scope:** Single self-contained script `stage8_v6_retraining.py`

---

## 1. Objective

Retrain the VAE anomaly detection model using V6 preprocessing (binary IP, binary duration, 4-period hour, 8-category activity, device fallback) and verify that localhost FPR drops from V5's 100% to <10%.

## 2. File Structure

```
ai-service/stage7/v6_retraining/
├── stage8_v6_retraining.py          # The single script
├── training_report.md               # Generated report
├── training_config.json             # Hyperparameters
├── training_history.json            # Per-epoch loss
├── training_loss.csv                # Per-epoch loss (CSV)
├── evaluation_distributions.csv     # MSE stats per group
├── experiment_metadata.json         # Full metadata
├── model_summary.json               # Architecture info
├── vae_model_v6_experiment.pth      # Experiment checkpoint
├── localhost_safety_analysis.csv    # FPR at multiple thresholds
└── threshold_sweep.csv              # Full threshold sweep
```

## 3. Script Architecture

Single file `stage8_v6_retraining.py` with 7 phases. No external imports from production utils — all V6 preprocessing functions are copied inline.

### Constants

```python
B = Path(__file__).resolve().parents[2]          # ai-service/
E = Path(__file__).resolve().parent              # v6_retraining/
V6_DIR = B / "stage7" / "v6"                     # V6 artifacts
SEED = 42
EPOCHS = 100
BS = 64
LR = 0.001
BETA = 0.001
PROD_THRESHOLD = 3.1496288776397705
FEATURE_COLUMNS = [
    "user_id", "activity", "status", "device", "ip_address",
    "duration_ms", "object_count", "hour", "day_of_week",
]
```

### Production Safety

```python
PROD_FILES = [
    B / "models/vae_model.pth",
    B / "models/deployment_config.json",
    B / "dataset/preprocessed/scaler.pkl",
    B / "dataset/preprocessed/label_encoders.pkl",
    B / "dataset/preprocessed/X_train.npy",
]
```

Hash before and after. Assert match.

---

## 4. Phase Details

### Phase 1: Data Loading & V6 Preprocessing

**Inputs:**
- `ai-service/dataset/retraining/retraining_dataset_combined_raw.csv` (15,329 rows)
- `ai-service/stage7/v6/v6_anomaly_raw.csv` (1,000 rows)
- `ai-service/stage7/v6/preprocessing_pipeline.json` (encoder classes + scaler params)

**Processing:**
1. Load raw CSV with `encoding='utf-8-sig'`
2. Load V6 anomalies CSV
3. Load preprocessing_pipeline.json
4. Apply `process_record_v6()` to ALL raw records
5. Reconstruct LabelEncoders from JSON class lists (NOT pickle)
6. Reconstruct scaler from JSON mean/scale arrays

**V6 Preprocessing Functions (copied inline from stage7_7_v6_dataset_redesign.py):**
- `map_network_scope(ip)` → Internal/External
- `map_has_telemetry(durasi_ms)` → 0.0/1.0
- `map_time_period(hour)` → 0/1/2/3
- `map_activity_v6(activity)` → 8 categories
- `parse_timestamp_wib(waktu)` → (hour, day_of_week)
- `process_record_v6(record)` → canonical dict

**Encoder Reconstruction:**
```python
from sklearn.preprocessing import LabelEncoder

def reconstruct_label_encoder(classes: list) -> LabelEncoder:
    enc = LabelEncoder()
    enc.fit(classes)
    return enc
```

**Scaler Reconstruction:**
```python
class V6Scaler:
    """Reconstruct StandardScaler from JSON params."""
    def __init__(self, mean, scale):
        self.mean_ = np.array(mean)
        self.scale_ = np.array(scale)
    def transform(self, X):
        return ((X - self.mean_) / self.scale_).astype("float32")
```

**Assertions:**
- Raw CSV loaded: 15,329 rows
- V6 anomalies loaded: 1,000 rows
- All 4 encoder class lists reconstructed correctly
- Scaler mean/scale arrays have length 9

### Phase 2: Source-Aware Split

**Logic:**
1. Filter raw CSV: `source_type == 'SYNTHETIC'` AND `candidate_type == 'NORMAL'` → 13,500 rows
2. Extract V6 anomaly `base_record_id` set from v6_anomaly_raw.csv (1,000 unique IDs)
3. Exclude ALL rows whose `source_id` is in the V6 base_record_id set → pool
4. Deterministic shuffle pool (seed=42)
5. Split pool: 70% train_normal, 15% val_normal, 15% test_normal
6. Split V6 anomalies: 50% val_anomaly (500), 50% test_anomaly (500) — deterministic shuffle
7. Extract REAL_DB records as localhost evaluation group

**Expected Counts:**
- Total synthetic normal: 13,500
- Excluded (V6 base): ~1,000
- Pool: ~12,500
- Train normal: ~8,750
- Val normal: ~1,875
- Test normal: ~1,875
- Val anomaly: 500
- Test anomaly: 500
- Localhost (REAL_DB): ~329

**Assertions:**
- No source_id overlap between train/val/test normal partitions
- No source_id overlap between normal partitions and anomaly partitions
- V6 anomaly base_record_ids NOT in any normal partition
- Val + test anomaly = 1,000 (all V6 anomalies)
- Each anomaly base_record_id is unique
- No NaN/Inf in any partition

### Phase 3: Encode & Scale

**Logic:**
1. Apply `process_record_v6()` to each partition (train/val/test normal, val/test anomaly, localhost)
2. Build 9-feature numeric matrix per partition:
   ```
   [user_id, enc(activity), enc(status), enc(device), enc(ip_address),
    duration_ms, object_count, hour, day_of_week]
   ```
3. Fit `V6Scaler` using train-normal mean/scale from JSON
4. Transform all partitions

**Assertions per partition:**
- Matrix shape: (n, 9)
- No NaN values
- No Inf values
- dtypes: float32

### Phase 4: Train VAE

**Architecture:**
```python
from services.model_loader import VariationalAutoencoder
```

**Training Loop:**
```python
torch.manual_seed(SEED)
np.random.seed(SEED)
random.seed(SEED)
torch.use_deterministic_algorithms(True, warn_only=True)

model = VariationalAutoencoder().to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
loader = DataLoader(
    TensorDataset(torch.from_numpy(X_train)),
    batch_size=BS, shuffle=True,
    generator=torch.Generator().manual_seed(SEED)
)

for epoch in range(EPOCHS):
    model.train()
    for (x,) in loader:
        x = x.float().to(device)
        optimizer.zero_grad()
        recon, mu, logvar = model(x)
        recon_loss = F.mse_loss(recon, x)
        kl_loss = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
        loss = recon_loss + BETA * kl_loss
        loss.backward()
        optimizer.step()
```

**Checkpoint:**
```python
torch.save(model.state_dict(), E / "vae_model_v6_experiment.pth")
```

**Assertions:**
- Final train total loss < 0.1 (convergence check)
- Checkpoint exists and reloads without error
- Reloaded model produces identical outputs for same input

### Phase 5: Evaluation

**MSE Computation:**
```python
def compute_mse(model, X):
    model.eval()
    with torch.no_grad():
        x = torch.from_numpy(X).float().to(device)
        recon, _, _ = model(x)
        return (x - recon).pow(2).mean(dim=1).cpu().numpy()
```

Groups:
- `mse_val_normal` — validation normal MSE
- `mse_test_normal` — test normal MSE
- `mse_val_anomaly` — validation anomaly MSE
- `mse_test_anomaly` — test anomaly MSE
- `mse_localhost` — localhost (REAL_DB) MSE

**Threshold Selection (from validation set):**
```python
y_val = np.r_[np.zeros(len(mse_val_normal)), np.ones(len(mse_val_anomaly))]
scores_val = np.r_[mse_val_normal, mse_val_anomaly]
precision, recall, thresholds = precision_recall_curve(y_val, scores_val)
f1_scores = 2 * precision * recall / (precision + recall + 1e-12)
best_idx = f1_scores.argmax()
threshold = thresholds[min(best_idx, len(thresholds) - 1)]
```

**Test Set Metrics:**
```python
y_test = np.r_[np.zeros(len(mse_test_normal)), np.ones(len(mse_test_anomaly))]
scores_test = np.r_[mse_test_normal, mse_test_anomaly]
roc_auc = roc_auc_score(y_test, scores_test)
pr_auc = average_precision_score(y_test, scores_test)
preds = scores_test >= threshold
tn, fp, fn, tp = confusion_matrix(y_test, preds).ravel()
```

**Output:**
- ROC-AUC, PR-AUC, F1, Precision, Recall, FPR, FNR
- Distribution stats (min, p25, median, p75, p95, p99, max, mean, std) per group

### Phase 6: Localhost Safety (CRITICAL)

**Multiple Threshold Evaluation:**
```python
thresholds_to_test = {
    "validation_optimal": threshold,
    "P95_val_normal": np.percentile(mse_val_normal, 95),
    "P99_val_normal": np.percentile(mse_val_normal, 99),
    "P99.5_val_normal": np.percentile(mse_val_normal, 99.5),
    "max_val_normal": np.max(mse_val_normal),
    "production": PROD_THRESHOLD,
}
```

For each threshold:
- Compute localhost FP count and FPR
- Compute test set precision, recall, F1

**Critical Assertions:**
- At validation optimal threshold: localhost FPR < 0.10 (target < 10%)
- At P99 threshold: localhost FPR < 0.05
- Ideal: localhost FPR = 0.00% at some reasonable threshold

**Output:**
- `localhost_safety_analysis.csv`
- `threshold_sweep.csv` (fine-grained sweep)

### Phase 7: Final Decision & Report

**Decision Logic:**
```python
f1_test >= 0.8 AND localhost_fpr < 0.10 → PASS
f1_test >= 0.8 AND localhost_fpr >= 0.10 → FAIL (anomaly detection OK but localhost unsafe)
f1_test < 0.8 → FAIL (anomaly detection insufficient)
```

**Report Generation:**
```markdown
# Stage 8 — V6 Controlled Retraining Experiment

## Configuration
- V6 preprocessing: binary IP, binary duration, 4-period hour, 8-category activity
- Architecture: 9-64-32-8-32-64-9 ReLU Dropout(0.2)
- Training: 100 epochs, lr=0.001, beta_kl=0.001, batch_size=64

## Training Results
- Final loss: ...
- Convergence: ...

## Test Set Metrics
- ROC-AUC: ...
- PR-AUC: ...
- F1: ...
- Precision: ...
- Recall: ...

## Localhost Safety
- FPR at validation threshold: ...%
- FPR at P99: ...%
- FPR at production threshold: ...%

## Decision
- PASS/FAIL: ...

## Comparison with V5
| Metric | V5 | V6 |
|--------|----|----|
| Localhost FPR | 100% | ...% |
| Test F1 | 0.996 | ... |
| ROC-AUC | 0.9998 | ... |
```

---

## 5. Data Flow Diagram

```
retraining_dataset_combined_raw.csv (15,329)
    │
    ├─ source_type=='SYNTHETIC' & candidate_type=='NORMAL' → 13,500 normal
    │     │
    │     ├─ Exclude V6 base_record_ids → ~12,500 pool
    │     │     │
    │     │     ├─ 70% → train_normal (~8,750)
    │     │     ├─ 15% → val_normal (~1,875)
    │     │     └─ 15% → test_normal (~1,875)
    │     │
    │     └─ ALL records → process_record_v6() → canonical
    │
    ├─ v6_anomaly_raw.csv (1,000)
    │     │
    │     ├─ 50% → val_anomaly (500)
    │     └─ 50% → test_anomaly (500)
    │
    └─ source_type=='REAL_DB' → localhost (~329)

    ALL groups → process_record_v6() → V6 encoders → V6 scaler → feature matrices
                                                            │
    train_normal ──────────────────────────────────────────→ VAE training
                                                            │
    val_normal + val_anomaly ──────────────────────────────→ threshold selection
                                                            │
    test_normal + test_anomaly ────────────────────────────→ test metrics
                                                            │
    localhost ─────────────────────────────────────────────→ FPR calculation
```

## 6. Key Differences from V5

| Aspect | V5 | V6 |
|--------|----|----|
| Preprocessing | `process_record()` from utils | `process_record_v6()` (inline) |
| IP encoding | 6-category LabelEncoder | Binary Internal/External |
| Duration | log1p(continuous) | Binary has_telemetry (0/1) |
| Hour | Raw 0-23 | 4-period (0/1/2/3) |
| Activity | 12 categories | 8 categories (rare→Administrasi) |
| Device fallback | None | Unknown Device→PC Windows |
| Encoder source | Fixed from utils | From V6 preprocessing_pipeline.json |
| Scaler source | Fit on train-normal | From V6 preprocessing_pipeline.json |
| Anomaly source | V5 anomalies (1,000) | V6 anomalies (1,000) |
| Script structure | 2 separate scripts | 1 combined script |
| Output dir | `experiment_v5/` | `v6_retraining/` |

## 7. Verification Steps

1. **Pre-split**: Assert V6 base_record_ids are subset of source_ids in raw data
2. **Post-split**: Assert no overlap between any partitions (normal vs normal, normal vs anomaly)
3. **Encode**: Assert all 9 features have no NaN/Inf after encoding+scaling
4. **Train**: Assert convergence (loss decreasing, final loss < threshold)
5. **Checkpoint**: Assert reload produces identical MSE
6. **Threshold**: Assert validation F1 > 0.8
7. **Localhost**: Assert FPR < 10% at validation threshold (PRIMARY SUCCESS CRITERION)
8. **Production**: Assert production artifacts untouched (SHA-256 match)
9. **Determinism**: Assert seed=42 used everywhere; optional 2-run reproducibility check

## 8. Risk Mitigation

- **Risk**: V6 preprocessing introduces new NaN values for edge cases in raw data
  - **Mitigation**: process_record_v6() has fallback handling for all fields
- **Risk**: Encoder mismatch (unseen categories in test/localhost)
  - **Mitigation**: V6 encoder classes cover all mapped categories; UNKNOWN fallback
- **Risk**: V6 anomaly base_record_ids not found in raw data
  - **Mitigation**: Phase 1 assertion checks this before proceeding
- **Risk**: Localhost FPR still high
  - **Mitigation**: Phase 6 evaluates multiple thresholds; report clearly states PASS/FAIL
