# 87 — Rencana Eksekusi Aturan Tahap 6

Acuan: `64_dataset_rule_decision_matrix.csv`, `65_dataset_cleaning_rules.md`, `66_dataset_before_after_spec.md`, `70_stage5_decision_summary.md`. Prinsip: tindakan yang tidak jelas disetujui = TIDAK dieksekusi.

## RULE_APPLIED (dieksekusi pada Stage 6)
| Rule | Tindakan | Artefak |
|---|---|---|
| A (Timestamp) | NO modification — validasi before/after = 0 perubahan | 88 |
| B (Working hours) | Metadata/analisis saja; tidak menyentuh record | 89 |
| C (Weekend) | Protektif — validasi count tetap 4.198 | 89 |
| D (Holiday) | Protektif — kalender SKB 2025 sebagai metadata; count tetap 1.124 | 89 |
| E (Activity — interim) | Artefak pemetaan kanonik DOCUMENT_ONLY (tanpa rename dataset) | 90 |
| K/L/M/O (Path, Hash, Labels, Missing) | Pemeriksaan pemisahan & non-imputasi (protective checks) | 92, 93, 94 |
| N (Duplicate) | Verification-only scan | 72, 73 |
| P (Synthetic/real separation) | Validasi real tidak masuk training set | 95 |

## RULE_VALIDATION_ONLY
- Seluruh baris tabel di atas bersifat validasi/protektif — satu-satunya penulisan data adalah **salinan byte-identik** `audit_log_dataset_stage6.csv` untuk reproducibility.

## RULE_DEFERRED
- E lanjutan (penyelarasan kamus + aktivitas baru): **DEFERRED_TO_GENERATOR_V2**.
- G/H/I/J (IP, device, duration, object_count pada data REAL): **DEFERRED_TO_APPLICATION_DATA_CAPTURE** — perbaikan di middleware/aplikasi, bukan di dataset existing.

## RULE_NOT_APPLIED
- Regenerasi timestamp baru, penghapusan weekend/holiday/luar-jam, imputasi/fabrikasi nilai apa pun, penambahan hash/path ke fitur, penggabungan data real, retraining/threshold — semuanya TIDAK disetujui → NOT APPLIED.

## Hasil yang diharapkan
DATASET PRESERVED — NO ROW-LEVEL TRANSFORMATION APPROVED. Salinan Stage 6 identik (SHA256_MATCH = TRUE).
