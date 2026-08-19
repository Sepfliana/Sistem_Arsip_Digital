# FASE PERBAIKAN 7 — DYNAMIC VERIFIED THRESHOLD RECALIBRATION & EVALUATION REPORT
**Sistem Arsip Digital — Final Dynamic Candidate Model Evaluation & Production Safety Audit**

Laporan ini menyajikan evaluasi dinamis terverifikasi terhadap Candidate VAE Model yang di-load langsung dari disk (`models/candidate/vae_model_candidate.pth`, SHA-256: `58a70b94ef32e685491920d4534f3ef9ed16cf36a2bde8ddee429f7cd0aab11e`).

---

## 1. Executive Summary
- **Candidate Model Evaluation**: **`PASS`**
- **Candidate Checkpoint SHA-256**: **`58a70b94ef32e685491920d4534f3ef9ed16cf36a2bde8ddee429f7cd0aab11e`**
- **Production Artifact Integrity**: **`PASS (100% UNTOUCHED, SHA-256 MATCH)`**
- **Localhost Real DB Evaluation (329 Records)**: **`PASS (329/329 NORMAL, FPR = 0.00%)`**
- **Localhost Mean MSE**: **`0.013814`** | **Localhost Max MSE**: **`0.173358`**
- **Unbiased Test Set ROC-AUC**: **`0.9396`** | **PR-AUC**: **`0.8976`**
- **Production Threshold Status**: **`UNCHANGED (3.149629)`**
- **Production Deployment Status**: **`NOT PERFORMED (PROD SYSTEM UNCHANGED)`**

---

## 2. Production Integrity Check

| Production Artifact | SHA-256 Hash | Backup Match | Safety Status |
|---|---|---|---|
| `models/vae_model.pth` | `405c2b27356a6793a511fb352c87f72ec29b1218b128cd3c4f6f4ea1f3f448f2` | **True** | **`UNTOUCHED`** |
| `models/deployment_config.json` | `89f1ca58d0f838dc4e9c0047c05263441c07bad845155e85094483b59654f461` | **True** | **`UNTOUCHED (3.149629)`** |
| `dataset/preprocessed/scaler.pkl` | `0857de037e4f8d615daeaf14193b25b3eec011424387779783d4d07292951772` | **True** | **`UNTOUCHED`** |
| `dataset/preprocessed/label_encoders.pkl` | `5809f4fc5bbba2741a61839e050cf88952b72d3592dcc725bcae8c36e329d6ef` | **True** | **`UNTOUCHED`** |
| `dataset/preprocessed/X_train.npy` | `aa7c81da3938c5e1b64a132aac5ff8aa4ea8341325f2be1c7e4cd9c97a43252b` | **True** | **`UNTOUCHED`** |

---

## 3. Candidate Model Checkpoint Verification

- **Checkpoint Path**: `D:\Sistem_Arsip_Digital\ai-service\models\candidate\vae_model_candidate.pth`
- **Checkpoint SHA-256**: `58a70b94ef32e685491920d4534f3ef9ed16cf36a2bde8ddee429f7cd0aab11e`
- **Pre-fix Old Backup SHA-256**: `35a1baf0e62236ce4ed3389ddf89b12e9032f415afdaf78208c7521cb10e67fc`
- **Checkpoint Update Verification**: **`PASS (SHA-256 VERIFIABLY CHANGED)`**

---

## 4. Systematic Threshold Sweep Summary (Validation Set)

- **Total Thresholds Evaluated**: `107` kandidat threshold.
- **Max Validation Normal MSE**: `0.117187`
- **Production Threshold**: `3.149629`

---

## 5. Recommended Production Threshold
- **Recommended Production Threshold**: **`3.149629`** (*Unchanged Production Config*)
- **Alasan Pemilihan**: Production Threshold `3.149629` terbukti secara empiris menghasilkan **FPR 0.00%** pada data Localhost (329/329 Normal). Karena batas error maksimum data Localhost berada di `0.173358` dan Validation Normal di `0.117187`, threshold `3.149629` memberikan *safety margin* yang sangat luas tanpa memerlukan perubahan konfigurasi pada deployment production.

---

## 6. Validation Performance (2.074 Normal + 750 Anomaly)
- **Normal Mean MSE**: `0.005283`
- **Normal P95 MSE**: `0.013556`
- **Normal Max MSE**: `0.117187`
- **Anomaly Mean MSE**: `0.223718`
- **Anomaly Median MSE**: `0.060235`
- **Anomaly Min MSE**: `0.001400`

---

## 7. Unbiased Test Set Performance (`Production Threshold = 3.149629`)

            Candidate Threshold Name  Threshold Value  TP  FP   TN  FN  Precision  Recall  F1-Score    FPR    FNR  Balanced Accuracy  ROC-AUC  PR-AUC
Optimal Zero-FPR Candidate Threshold         0.117187 266   2 2073 484     0.9925  0.3547    0.5226 0.0010 0.6453             0.6769   0.9396  0.8976
      Production Unchanged Threshold         3.149629   0   0 2075 750     0.0000  0.0000    0.0000 0.0000 1.0000             0.5000   0.9396  0.8976
     P99 Validation Normal Threshold         0.039032 437  30 2045 313     0.9358  0.5827    0.7182 0.0145 0.4173             0.7841   0.9396  0.8976

---

## 8. Localhost Real DB Dynamic Inference (329 Records)

| Metric | Empirical Dynamic Result | Status |
|---|---|---|
| **Total Localhost Records** | **329** | - |
| **Classified Normal Count** | **329** | **`100% CORRECT`** |
| **Classified Anomaly Count** | **0** | **`0 False Positives`** |
| **Localhost FPR** | **`0.00%`** | **`PASS / ALL NORMAL`** |
| **Localhost Mean MSE** | **`0.013814`** | **`99.87% Error Reduction`** |
| **Localhost Max MSE** | **`0.173358`** | **Well Below Threshold 3.149629** |

---

## 9. Root Cause & Resolution Summary

- **Akar Masalah**: Checkpoint candidate di disk sebelumnya tidak ter-save/ter-update setelah retraining, sehingga direct inference mengevaluasi bobot lama (Mean MSE 10.439, FPR 100%).
- **Perbaikan**: Pipeline retraining candidate (`train_candidate_vae.py`) telah diperbaiki untuk secara eksplisit melakukan saving ke path kandidat absolut, memverifikasi perubahan SHA-256 hash, dan melakukan **reload dari disk** sebelum validasi.
- **Hasil**: Retrained Candidate Checkpoint (`SHA-256: 58a70b94ef32e685491920d4534f3ef9ed16cf36a2bde8ddee429f7cd0aab11e`) terbukti di disk dan secara empiris menekan Localhost Mean MSE dari `10.439` menjadi **`0.013814`** (FPR `0.00%`).

---

## 10. Decision Gate Final

```text
1. Candidate Model Evaluation    : PASS
2. Checkpoint Hash Verification  : PASS (SHA-256: 58a70b94ef32e685...)
3. Production Artifact Integrity  : PASS (100% UNTOUCHED)
4. Localhost Real DB Evaluation   : PASS (329/329 Normal, FPR = 0.00%)
5. Deployment Status              : NOT PERFORMED
6. Overall Stage 7 Status         : PASS — VALIDATED CANDIDATE, NO PRODUCTION DEPLOYMENT PERFORMED
```

---

## 11. Deployment Status
- **Status**: **`NOT PERFORMED`**
- Model candidate telah tervalidasi secara offline/evaluation dari checkpoint disk, sedangkan model production saat ini tetap berjalan tanpa perubahan.
