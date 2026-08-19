# Stage 7.5 — V4 Validation

Generated valid: 1300 / 1500; archive rejections are retained separately.

## Per-type
```
anomaly_type,count,severity,mutated_features,min,p25,median,p75,p95,p99,max,mean,std,detect_normal_p95,detect_normal_max,overlap_normal_max
credential_takeover_compound,300,Severe,"waktu,aksi,ip_address,device",0.7484306,0.86990084,1.0085210500000001,1.16141985,1.28960597,1.3719284029999996,4.1158175,1.0341955089666666,0.25308342765407593,1.0,1.0,0.0
offhours_sensitive_external_access,400,Moderate,"waktu,aksi,ip_address",0.67415506,0.9801222125,1.0630064,1.13640275,1.2500556249999997,1.4205146009999972,1.9996839,1.058608103575,0.15355508251923458,1.0,1.0,0.0
scripted_rapid_failure,300,Moderate,"status,device,durasi_ms",0.014985387,0.03067739875,0.061398615,0.2520388225,0.3790327195,0.6937031738999986,0.9218724,0.15119763479333334,0.15209437113764865,1.0,0.45666666666666667,0.5433333333333333
suspicious_external_access,300,Mild,"ip_address,device",0.5976088,0.754449125,0.790705585,0.826380535,0.8853940975000001,0.9162969035999999,1.877615,0.7962344673333333,0.09255631061130441,1.0,1.0,0.0
```

## Overlap
```
threshold,value,anomaly_count_le,anomaly_pct_le
normal_p95,0.011473985388875008,0,0.0
normal_p99,0.03299706056714058,88,6.769230769230769
normal_max,0.1402665078639984,163,12.538461538461537
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
  "thresholds": {
    "production": {
      "value": 3.1496288776397705,
      "fpr": 0.0,
      "false_positive": 0
    },
    "normal_max": {
      "value": 0.1402665078639984,
      "fpr": 0.00303951367781155,
      "false_positive": 1
    },
    "normal_p99": {
      "value": 0.03299706056714058,
      "fpr": 0.06990881458966565,
      "false_positive": 23
    },
    "best_offline_v4_simulation": {
      "value": 0.011002919636666775,
      "fpr": 0.44680851063829785,
      "false_positive": 147
    }
  }
}
```

Production hashes captured after audit; candidate hash `58a70b94ef32e685491920d4534f3ef9ed16cf36a2bde8ddee429f7cd0aab11e`.

**V4 DATASET REJECTED — FURTHER REDESIGN REQUIRED**. No retraining or deployment performed.
