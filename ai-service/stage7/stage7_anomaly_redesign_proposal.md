# STAGE 7.5 — SYNTHETIC DATASET ANOMALY REDESIGN PROPOSAL
**Sistem Arsip Digital — Forensic Investigation & Controlled Synthetic Anomaly Generator Redesign**

Laporan dan proposal ini menyajikan investigasi mendalam terhadap generator anomali sintetis saat ini (`dataset/generator/anomaly.py`) serta merancang skema **redesign anomali sintetis terkontrol** berdasarkan hasil *forensic dataset audit Stage 7.5*.

---

## 1. Executive Summary
- **Investigasi Utama**: Evaluasi statistik membuktikan bahwa kendala utama $F1$-score bukan sekadar penentuan threshold, melainkan **desain anomali sintetis saat ini yang 100% didasarkan pada mutasi 1-fitur independen (single-feature mutation)** yang sangat halus dan terdistorsi oleh variasi data normal.
- **Akar Masalah `login_luar_jam`**: 30% dari total data anomali sintetis hanya mengubah `hour` menjadi 0–6 WIB. Padahal, data operasional riil (termasuk audit log PostgreSQL) terbukti **memiliki aktivitas normal yang sah pada rentang jam 0–6 WIB (1.19% normal, 34.65% Localhost)**.
- **Dampak Feature Dilution**: Dalam arsitektur VAE 9-fitur, mutasi 1 fitur halus hanya menyumbang $1/9$ (11,11%) dari loss MSE rekonstruksi, sementara 8 fitur lainnya bernilai normal murni. Akibatnya, 67,33% anomali sintetis memiliki reconstruction MSE $\le$ Normal Max (`0.1469`).
- **Proposal Redesign**: Mengganti mutasi 1-fitur independen dengan **multivariate threat scenario (2 s/d 4 fitur terkorolari)** yang sesuai dengan *Threat Model* Sistem Arsip Digital tanpa membuat anomali ekstrem yang tidak realistis.
- **Status Production & Deployment**: **`100% UNTOUCHED`**, Retraining = **`NOT PERFORMED`**, Deployment = **`NOT PERFORMED`**, Stage 8 = **`NOT STARTED`**.

---

## 2. Current Generator Diagnosis & Forensic Evidence

### A. Diagnosa Penyebab Kegagalan `login_luar_jam`
Dalam `dataset/generator/anomaly.py`, tipe anomali `login_luar_jam` dibuat dengan aturan:
```python
if anomaly == "login_luar_jam":
    event["timestamp"] = event["timestamp"].replace(hour=random.randint(0, WORK_START - 1))
```
- **Statistik Distribusi Jam Normal vs Anomali**:
  - Normal Candidates (`X_train_candidate.npy`): Rentang jam = **0 s/d 23 WIB** (Mean = 18.27, Std = 3.41).
  - Real Localhost DB: Rentang jam = **0 s/d 23 WIB** (Mean = 18.27, 114 event berada di jam 0–6 WIB).
  - Anomali `login_luar_jam`: Rentang jam = **0 s/d 6 WIB** (Mean = 3.00).
- **Kesimpulan Forensic**: Jam 0–6 WIB **bukanlah anomali dalam domain operasional Sistem Arsip Digital**. Menjadikan `hour < 7` sebagai satu-satunya kriteria anomali menciptakan tumpang tindih statistik 100% dengan data normal, sehingga VAE merekonstruksi record ini dengan MSE sangat rendah (`0.0035`).

### B. Masalah Single-Feature Anomaly Mutation & Feature Dilution
- **Proporsi Single-Feature Mutation Saat Ini**: **100.00%** (7 dari 7 tipe anomali di `anomaly.py` hanya memodifikasi 1 fitur secara independen).
- **Mekanisme Feature Dilution**:
  $$	ext{MSE} = rac{1}{9} \sum_{i=1}^{9} (z_i - \hat{z}_i)^2$$
  Ketika hanya 1 fitur dimutasi secara halus (misal `hour` bergeser dari 10 ke 4), 8 fitur lainnya memberikan error nol ($pprox 0.001$). Total MSE rekonstruksi terdistilasi menjadi $pprox 0.0035$, jauh di bawah batas maksimum normal (`0.1469`).

---

## 3. Threat Model Alignment (Sistem Arsip Digital)

Anomali sintetis baru dirancang berdasarkan skenario ancaman siber riil pada aplikasi arsip digital:

Scenario ID                                Threat Scenario                                                                Observable Evidence                    Features Mutated Severity Tier Expected VAE Detectability
      TM-01           Credential Misuse / Account Takeover                   Login / Kelola User from Public IP + Virtual Machine + Off-hours  hour, ip_address, device, activity        Severe     VERY HIGH (MSE > 1.50)
      TM-02                    Off-Hours Privileged Access Off-hours (0-5 AM) + Sensitive Activity (Kelola User / Laporan) + Unusual Duration         hour, activity, duration_ms      Moderate          HIGH (MSE > 0.40)
      TM-03 Automated Mass Archive Exfiltration (Scraping)            Mass Object Access (50-200 objects) + Extremely Rapid Duration (1-50ms) object_count, duration_ms, activity        Severe     VERY HIGH (MSE > 1.20)
      TM-04      Suspicious External Infrastructure Access                                       Public IP + Virtual Machine / Unknown Device                  ip_address, device      Moderate          HIGH (MSE > 0.80)
      TM-05            Mass Unauthorized Archive Borrowing                        Peminjaman / Verifikasi + Object Count (30-100) + Off-hours        object_count, activity, hour      Moderate          HIGH (MSE > 0.35)
      TM-06           Brute-Force / Rapid Scripted Attempt                                  Status Gagal + Duration (1-20ms) + Unknown Device         status, duration_ms, device      Moderate          HIGH (MSE > 0.45)
      TM-07         Subtle External Probe (Single-Feature)                               Public IP Address with standard operational activity                          ip_address          Mild      MODERATE (MSE > 0.18)

---

## 4. Perbandingan Skema Desain: CURRENT vs PROPOSED DESIGN

| Parameter Desain | CURRENT DESIGN (`anomaly.py`) | PROPOSED REDESIGN (Terperinci) | Rationale & Dampak |
|---|---|---|---|
| **Jumlah Fitur Dimutasi** | 100% Single-Feature (1 Fitur) | **Compound Multi-Feature (2 s/d 4 Fitur)** | Mengeliminasi feature dilution VAE secara ilmiah. |
| **Definisi `login_luar_jam`** | Murni `hour < 7` | **`hour < 7` + Privileged Activity / Public IP** | Mengeliminasi false positive pada aktivitas normal jam 0–6 WIB. |
| **Variasi IP Anomali** | Random IP String acak | **Public IP + Region Distorsi + Status Check** | Merepresentasikan akses infrastruktur eksternal/untrusted. |
| **Mutasi Durasi & Status** | Murni `duration < 100ms` | **Duration 1-20ms + Status Gagal + Unknown Device** | Merepresentasikan serangan automated brute-force / scripting. |
| **Mutasi Exfiltration** | Murni `object_count 30-100` | **Object Count 50-200 + Duration < 50ms + Access Activity** | Merepresentasikan ekstraksi / pencurian arsip massal. |
| **Komposisi Severity** | Tidak Terstruktur (Random) | **Mild (20%), Moderate (50%), Severe (30%)** | Menyediakan gradien evaluasi threshold yang realistis. |

---

## 5. Proposed New Anomaly Taxonomy & Severity Tiers

 Severity Tier        Proposed Anomaly Type                        Features Changed Expected Realism    Expected Detectability
    Mild (20%)     external_ip_single_probe                          1 (ip_address)             High Moderate (MSE ~0.20-0.50)
    Mild (20%)        unusual_device_single                              1 (device)             High Moderate (MSE ~0.15-0.30)
Moderate (50%)    offhours_sensitive_access                      2 (hour, activity)        Very High     High (MSE ~0.40-0.80)
Moderate (50%)      offhours_external_login                    2 (hour, ip_address)        Very High     High (MSE ~0.80-1.20)
Moderate (50%)       scripted_rapid_failure         3 (status, duration_ms, device)             High     High (MSE ~0.50-0.90)
  Severe (30%)   mass_exfiltration_scraping 3 (object_count, duration_ms, activity)        Very High    Very High (MSE > 1.20)
  Severe (30%) credential_takeover_compound  4 (hour, ip_address, device, activity)   Extremely High    Very High (MSE > 2.00)

---

## 6. Anti-Leakage & Validation Plan (Sebelum Retraining)

Sebelum dataset baru digunakan untuk retraining kandidat di masa depan, rantai validasi berikut **WAJIB dipenuhi**:

1. **Strict Zero Contamination in Normal Training Set**:
   `X_train_candidate.npy` (9,680 baris) tetap **100.00% bersih dari anomali** (hanya berisi data normal sintetis & normal Localhost riil).
2. **Fixed Random Seed**:
   Generator menggunakan `random.seed(42)` dan `np.random.seed(42)` untuk menjamin *100% deterministic reproducibility*.
3. **Localhost Real DB Safety Gate Check**:
   Dataset anomali baru **TIDAK BOLEH mengandung atau memuat parameter yang mengatribusi record Localhost (`127.0.0.1`, `::1`) sebagai anomali**. 329 record Localhost riil wajib diuji dan menghasilkan **Localhost FPR = 0.00%**.
4. **Independent Split Isolation**:
   Tidak ada record anomali yang tumpang tindih antara Train, Validation, dan Test split.
5. **Preprocessing Contract v2 Compliance**:
   Dataset baru diolah strictly menggunakan contract v2 (9 fitur: `user_id`, `activity`, `status`, `device`, `ip_address`, `duration_ms`, `object_count`, `hour`, `day_of_week`).

---

## 7. Production Safety Verification

- `models/vae_model.pth`: SHA-256 `405c2b27356a6793a511fb352c87f72ec29b1218b128cd3c4f6f4ea1f3f448f2` (**100% MATCH BACKUP**)
- `models/deployment_config.json`: SHA-256 `89f1ca58d0f838dc4e9c0047c05263441c07bad845155e85094483b59654f461` (**100% MATCH BACKUP, THRESHOLD 3.149629**)
- `dataset/preprocessed/scaler.pkl`: SHA-256 `0857de037e4f8d615daeaf14193b25b3eec011424387779783d4d07292951772` (**100% MATCH BACKUP**)
- `dataset/preprocessed/label_encoders.pkl`: SHA-256 `5809f4fc5bbba2741a61839e050cf88952b72d3592dcc725bcae8c36e329d6ef` (**100% MATCH BACKUP**)
- `dataset/preprocessed/X_train.npy`: SHA-256 `aa7c81da3938c5e1b64a132aac5ff8aa4ea8341325f2be1c7e4cd9c97a43252b` (**100% MATCH BACKUP**)


---

## 8. Final Decision Gate

```text
============================================================
STAGE 7.5 — ANOMALY REDESIGN INVESTIGATION COMPLETE
============================================================

Root Cause Utama         : Generator anomali saat ini menggunakan mutasi 1-fitur independen yang terlalu ringan dan terdistilasi oleh VAE.
Root Cause Sekunder      : Definisi `login_luar_jam` murni `hour < 7` mengalami tumpang tindih statistik dengan data operasional normal jam 0-6 WIB.

Execution Status         : PASS
Dataset Analysis         : COMPLETE & PROPOSED
Production Integrity     : PASS (100% UNTOUCHED)
Production Threshold     : UNCHANGED (3.149629)
Retraining               : NOT PERFORMED
Deployment               : NOT PERFORMED
Stage 8 Status           : NOT STARTED

STATUS: READY FOR HUMAN REVIEW & PROPOSAL APPROVAL
============================================================
```
