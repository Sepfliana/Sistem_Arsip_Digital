# V6 Anomaly Generator Design

**Stage:** 7.7 — V6 Dataset Redesign
**Seed:** 42
**Target:** 1,000 anomaly records (source-aware, joint-rare)

---

## Anomaly Taxonomy

### Type 1: suspicious_external_access (300 records, Mild)

**Threat model:** An external IP accesses the system from a virtual machine — possible scanner or compromised host.

**Mutations (raw domain):**
- `ip_address` → `'8.8.8.8'` (maps to "External" in V6)
- `device` → `'Virtual Machine'`

**Joint combination:** (Night/Morning/Afternoon/Evening, *, Virtual Machine, External)
**Expected joint frequency:** <0.1% (VM + External is rare in training)

---

### Type 2: offhours_sensitive_external_access (400 records, Moderate)

**Threat model:** A sensitive administrative action (user management) performed from an external network during off-hours.

**Mutations (raw domain):**
- `waktu` → forced to Night hour bucket (hour 0-5 WIB)
- `aksi` → `'KELOLA USER'` (maps to "Kelola User")
- `ip_address` → `'8.8.8.8'` (maps to "External")

**Joint combination:** (Night, Kelola User, *, External)
**Expected joint frequency:** <0.1% (night + admin + external is rare)

---

### Type 3: credential_takeover_compound (300 records, Severe)

**Threat model:** Compound pattern suggesting credential takeover — off-hours security/2FA activity from external VM.

**Mutations (raw domain):**
- `waktu` → forced to Night hour bucket (hour 0-5 WIB)
- `aksi` → `'SETUP 2FA'` (maps to "Administrasi" in V6 reduced vocabulary)
- `ip_address` → `'8.8.8.8'` (maps to "External")
- `device` → `'Virtual Machine'`

**Joint combination:** (Night, Administrasi, Virtual Machine, External)
**Expected joint frequency:** <0.1% (compound of all rare elements)

---

## Constraints

1. **Joint rarity:** Primary joint combination frequency ≤0.1% in normal training data
2. **Source disjointness:** No base record ID overlaps with validation/test partitions
3. **No duplicates:** Each generated row has a unique base_record_id
4. **Raw domain only:** All mutations applied to raw fields; canonical encoding via process_record_v6()
5. **Removed types from V4/V5:**
   - `mass_archive_access` — joint-common pattern, undetectable
   - `scripted_rapid_failure` — joint-rare but model-indistinguishable from normal

---

## V6-Specific Changes vs V5

| Aspect | V5 | V6 |
|--------|-----|-----|
| IP encoding | 6-category | Binary Internal/External |
| Duration encoding | log1p continuous | Binary has_telemetry |
| Hour encoding | 0-23 integer | 4-period categorical |
| Device fallback | None | Unknown Device → PC Windows |
| Activity vocabulary | 12 categories | 8 categories (rare → Administrasi) |
| credential_takeover activity | "Keamanan & 2FA" | "Administrasi" (merged) |

---

## Determinism

- Seed=42 for all random operations
- Base records sampled with `random_state=42`
- No replacement, no stochastic rejection
- Output CSV hash verifiable via SHA-256
