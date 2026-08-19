# Stage 8 Iteration 2 -- V7 Targeted Fix + Retraining

Experiment-only checkpoint.  No production deployment.

## Configuration
- Architecture: 9-64-32-8-32-64-9 ReLU Dropout(0.2)
- Training: 100 epochs, lr=0.001, beta_kl=0.001, batch_size=64
- V7 Fixes:
  1. Status preprocessing: unseen status -> 'Berhasil' (mode of train_normal)
  2. Training data: 70% synthetic + 30% localhost (no leakage)
- Train rows: 766

## Final Training Loss
0.036811

## Test Set Metrics
```json
{
  "roc_auc": 0.9936,
  "pr_auc": 0.908,
  "f1": 0.867,
  "precision": 0.8104,
  "recall": 0.932,
  "fpr": 0.0182,
  "threshold_f1_optimal": 0.203241,
  "threshold_safe_p95": 0.085619,
  "threshold_safe_p99": 0.285894,
  "threshold_safe_p995": 0.465232,
  "threshold_max_val_normal": 1.172608
}
```

## Localhost Safety (using localhost_eval only)
```json
{
  "validation_f1_optimal": {
    "threshold": 0.203241,
    "localhost_eval_fp": 70,
    "localhost_eval_fpr": 0.7071,
    "localhost_eval_n": 99
  },
  "safe_p95": {
    "threshold": 0.085619,
    "localhost_eval_fp": 88,
    "localhost_eval_fpr": 0.8889,
    "localhost_eval_n": 99
  },
  "safe_p99": {
    "threshold": 0.285894,
    "localhost_eval_fp": 22,
    "localhost_eval_fpr": 0.2222,
    "localhost_eval_n": 99
  },
  "safe_p995": {
    "threshold": 0.465232,
    "localhost_eval_fp": 0,
    "localhost_eval_fpr": 0.0,
    "localhost_eval_n": 99
  },
  "max_val_normal": {
    "threshold": 1.172608,
    "localhost_eval_fp": 0,
    "localhost_eval_fpr": 0.0,
    "localhost_eval_n": 99
  },
  "production": {
    "threshold": 3.149629,
    "localhost_eval_fp": 0,
    "localhost_eval_fpr": 0.0,
    "localhost_eval_n": 99
  }
}
```

## Domain Gap
- localhost_eval_min_mse: 0.002320
- localhost_eval_max_mse: 0.345284
- normal_max_mse: 1.574630
- gap: -1.572309

## Production Integrity
- Match: True
