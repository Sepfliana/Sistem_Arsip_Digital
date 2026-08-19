# Stage 8 -- V6 Controlled Retraining Experiment

Experiment-only checkpoint.  No production deployment.

## Configuration
- Architecture: 9-64-32-8-32-64-9 ReLU Dropout(0.2)
- Training: 100 epochs, lr=0.001, beta_kl=0.001, batch_size=64
- V6 preprocessing: binary IP, binary duration, 4-period hour, 8-category activity
- Train rows: 8750

## Final Training Loss
0.011038

## Test Set Metrics
```json
{
  "roc_auc": 1.0,
  "pr_auc": 0.9999,
  "f1": 0.999,
  "precision": 0.998,
  "recall": 1.0,
  "fpr": 0.0005,
  "threshold_f1_optimal": 0.112091,
  "threshold_safe_p99": 0.013887
}
```

## Localhost Safety
```json
{
  "validation_f1_optimal": {
    "threshold": 0.112091,
    "localhost_fp": 329,
    "localhost_fpr": 1.0,
    "localhost_n": 329
  },
  "safe_p99": {
    "threshold": 0.013887,
    "localhost_fp": 329,
    "localhost_fpr": 1.0,
    "localhost_n": 329
  },
  "production": {
    "threshold": 3.149629,
    "localhost_fp": 0,
    "localhost_fpr": 0.0,
    "localhost_n": 329
  },
  "p95_val_normal": {
    "threshold": 0.006456,
    "localhost_fp": 329,
    "localhost_fpr": 1.0,
    "localhost_n": 329
  },
  "max_val_normal": {
    "threshold": 0.188254,
    "localhost_fp": 329,
    "localhost_fpr": 1.0,
    "localhost_n": 329
  }
}
```

## Domain Gap
- localhost_min_mse: 2.182856
- normal_max_mse: 0.188254
- gap: 1.994602

## Production Integrity
- Match: True
