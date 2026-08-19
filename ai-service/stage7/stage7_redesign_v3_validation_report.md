# Stage 7.5 — V3 Validation

## Pipeline
Raw synthetic mutation → `process_record()` (including `log1p`) → candidate encoders → candidate scaler → existing candidate VAE. No retraining.

## MSE distribution
```
group,count,min,p25,median,p75,p95,p99,max,mean,std
normal_test,2025,0.00025109885609708726,0.002251530298963189,0.0034799117129296064,0.005310149863362312,0.011473985388875008,0.03299706056714058,0.14026649296283722,0.004880368709564209,0.006851712241768837
v3_anomaly,1500,0.0018103644251823425,0.02354617416858673,0.33175045251846313,0.9005581140518188,1.163415551185608,1.277530550956726,2.937699556350708,0.49110928177833557,0.46018892526626587
localhost,329,0.0005232472904026508,0.005376506596803665,0.009691813960671425,0.01547438558191061,0.03797222673892975,0.08623509109020233,0.17246811091899872,0.01381031982600689,0.01704682782292366
```

## Offline metrics
```
{
  "roc_auc": 0.9503288888888889,
  "pr_auc": 0.9499053238083869,
  "best_f1": 0.5979669124970892,
  "best_threshold": 0.011000707745552063,
  "precision": 0.920059215396003,
  "recall": 0.8286666666666667,
  "fpr": 0.05333333333333334,
  "fnr": 0.17133333333333334
}
```

## Localhost
```
{
  "count": 329,
  "min": 0.0005232472904026508,
  "p25": 0.005376506596803665,
  "median": 0.009691813960671425,
  "p75": 0.01547438558191061,
  "p95": 0.03797222673892975,
  "p99": 0.08623509109020233,
  "max": 0.17246811091899872,
  "mean": 0.01381031982600689,
  "std": 0.01704682782292366,
  "fpr_production_threshold": 0.0,
  "fpr_best_offline_threshold": 0.44680851063829785
}
```

## Decision
**DATASET V3 REJECTED — FURTHER REDESIGN REQUIRED.**

The raw-domain pipeline is valid, but per-type detectability is not: `mass_archive_access` has only 1.45% detection above Normal MAX and `offhours_privileged_access` only 14.4%. The offline best threshold causes 44.68% Localhost FPR. These failures prohibit controlled retraining review.

Production hashes unchanged: `True`.
