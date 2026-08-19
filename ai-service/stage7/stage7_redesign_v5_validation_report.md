# Stage 7.5 — V5 Validation

Mass archive removed: the feature set cannot observe extraction volume. Scripted rapid failure excluded: joint-rare but model-indistinguishable.

## Metrics
```
{
  "roc_auc": 1.0,
  "pr_auc": 1.0,
  "best_f1": 0.9999999999995,
  "best_threshold": 0.5976088047027588,
  "precision": 1.0,
  "recall": 1.0,
  "fpr": 0.0,
  "fnr": 0.0
}
```

## Per type
```
anomaly_type,count,min,p25,median,p75,p95,p99,max,mean,std,detect_p95,detect_p99,detect_max,overlap_max
credential_takeover_compound,300,0.7197970151901245,0.8763951659202576,1.0238553285598755,1.1576321125030518,1.2841130495071411,1.801955223083496,4.202725887298584,1.0495227575302124,0.3232135772705078,1.0,1.0,1.0,0.0
offhours_sensitive_external_access,400,0.674155056476593,0.9801222085952759,1.0630064010620117,1.1364027261734009,1.2500555515289307,1.420517921447754,1.9996838569641113,1.058608055114746,0.15355508029460907,1.0,1.0,1.0,0.0
suspicious_external_access,300,0.5976088047027588,0.7544491291046143,0.7907055616378784,0.8263805508613586,0.8853939771652222,0.9162970185279846,1.877614974975586,0.7962344288825989,0.09255631268024445,1.0,1.0,1.0,0.0
```

## Localhost
```
{
  "mse": {
    "min": 0.0005232472904026508,
    "p25": 0.0053765070624649525,
    "median": 0.009691814891994,
    "p75": 0.01547438744455576,
    "p95": 0.03797222673892975,
    "p99": 0.08623509854078293,
    "max": 0.17246811091899872,
    "mean": 0.01381031982600689,
    "std": 0.01704682782292366
  },
  "production_threshold": {
    "value": 3.1496288776397705,
    "fpr": 0.0,
    "fp": 0
  },
  "normal_max": {
    "value": 0.1402665078639984,
    "fpr": 0.00303951367781155,
    "fp": 1
  },
  "best_offline": {
    "value": 0.5976088047027588,
    "fpr": 0.0,
    "fp": 0
  }
}
```

**V5 DATASET ACCEPTED FOR CONTROLLED RETRAINING REVIEW** only if production hashes match and Localhost production FPR is zero; this is not authorization to retrain.
