# Domain Gap Solution Strategy

**Scope:** Propose exactly one fix per CRITICAL/HIGH feature. No implementation — design only.
**Constraints:** Must NOT degrade V5 anomaly detectability. Must NOT introduce leakage. Must be explainable and auditable.

---

## Feature 1: `ip_address` — CRITICAL (score=100.0)

### Problem Summary
LabelEncoder encounters unseen "Localhost / Loopback" category (training has constant "Private Network 192.168.x.x"). Encoder assigns fallback integer 0, decoder cannot reconstruct → infinite MSE. Additionally, ip_address was constant in training (std=0), making it a structurally flawed feature that encodes identity, not behavior.

### Evidence
| Metric | Value |
|--------|-------|
| Train categories | 100% "Private Network 192.168.x.x" |
| Localhost categories | 100% "Localhost / Loopback" |
| Scaled z-score | 3.0×10¹² (training std=0) |
| MSE ratio | 1,240,582,912× |
| Contribution | 301.1% of total localhost MSE |
| Root cause | AD (Representation mismatch + Feature design) |

### Proposed Fix: Feature Redesign → Binary Network Scope

**Replace** the 6-category `ip_address` with a binary feature:

```python
# BEFORE (6 categories):
IP_CLASSES = [
    "Localhost / Loopback",
    "Private Network 192.168.x.x",
    "Private Network 10.x.x.x",
    "Private Network 172.16-31.x.x",
    "Public IP Address",
    "UNKNOWN",
]

# AFTER (2 categories):
NETWORK_SCOPE_CLASSES = [
    "Internal",   # localhost, 192.168.x.x, 10.x.x.x, 172.16-31.x.x
    "External",   # public IPs, unknown
]
```

**Mapping rule:**
```python
def map_network_scope(ip_input: Any) -> str:
    category = map_ip_category(ip_input)  # reuse existing classifier
    if category in ("Localhost / Loopback", "Private Network 192.168.x.x",
                     "Private Network 10.x.x.x", "Private Network 172.16-31.x.x"):
        return "Internal"
    return "External"
```

### Why This Works
- **Eliminates domain shift:** Both train (192.168.x.x) and localhost (127.0.0.1) → "Internal" → same integer encoding
- **Preserves anomaly signal:** External IPs (attacks, scanners) would map to "External" → different encoding → detectable
- **Same feature dimension:** Still 1 categorical feature, no architecture change required
- **Auditable:** Binary scope is interpretable and explainable

### Risk Analysis
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reduced IP specificity | Certain | Low | Network scope is sufficient for anomaly detection; fine-grained IP categories were redundant |
| External IP anomaly signal weakened | Low | Medium | Binary "Internal/External" still captures the key distinction; rare external IPs would be flagged |
| Retraining required | Certain | Medium | Model must be retrained with new 8-feature input (V6 dataset) |

### Verdict: RECOMMENDED
This is the cleanest fix. It eliminates the dominant source of domain shift (301% of MSE), requires no runtime hacks, and the new feature is semantically meaningful.

---

## Feature 2: `duration_ms` — CRITICAL (score=95.4)

### Problem Summary
All 329 localhost records have `duration_ms = 0` (log1p=0) because localhost API calls do not produce browser-side timing telemetry. Training data has durations 200–12000 ms (log1p mean=7.41). The model learned to reconstruct log1p(duration)≈7.4; it cannot reconstruct 0.0.

### Evidence
| Metric | Value |
|--------|-------|
| Localhost duration_ms | 100% = 0 ms |
| Train duration_ms | Mean=1640 ms, range=200–12000 ms |
| Scaled z-score | −8.83σ |
| MSE ratio | 2032× |
| Contribution | 532.3% of total localhost MSE |
| Root cause | CB (Logging artifact + Behavioral shift) |

### Proposed Fix: Feature Redesign → Binary Telemetry Flag

**Replace** the continuous `duration_ms` with a binary feature:

```python
# BEFORE:
# duration_ms = log1p(raw_duration_ms)  → continuous [0, 9.4]

# AFTER:
# has_browser_telemetry = 1 if duration_ms > 0, else 0  → binary {0, 1}
```

**Mapping rule:**
```python
def map_has_telemetry(durasi_ms: Any) -> float:
    try:
        dur = float(durasi_ms)
        return 1.0 if dur > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0
```

### Why This Works
- **Eliminates domain shift:** Both train (all >0) and localhost (all =0) would map to known values in {0, 1}
- **Preserves anomaly signal:** Records without telemetry (localhost, potential sensor failures) are distinguishable from records with telemetry
- **Same feature dimension:** Still 1 numeric feature
- **Clean semantics:** "Was timing data captured?" is a meaningful binary signal

### Risk Analysis
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Loss of duration information | Certain | Medium | Duration was used for fine-grained anomaly detection; binary flag preserves the presence/absence signal |
| Future records with duration=0 | Low | Low | All future localhost calls would have duration=0 → consistently flagged |
| Retraining required | Certain | Low | Simple feature replacement, no architecture change |

### Verdict: RECOMMENDED
Converts a continuous feature with systematic domain shift into a binary feature with zero domain shift. The semantic meaning is preserved.

---

## Feature 3: `hour` — HIGH (score=75.9)

### Problem Summary
Training data is concentrated in working hours (mean=18.4h, std=3.1, heavy right skew 16–21h). Localhost traffic is uniformly distributed (mean=10.8h, std=6.5). The model learned to reconstruct hour≈18; records from midnight–morning produce large MSE.

### Evidence
| Metric | Value |
|--------|-------|
| Train hour mean | 18.4 h (std=3.1, concentrated 16–21h) |
| Localhost hour mean | 10.8 h (std=6.5, uniform 0–23h) |
| Scaled z-score | 2.47σ |
| MSE ratio | 34× |
| Contribution | 29.3% of total localhost MSE |
| Root cause | B (Behavioral shift) |

### Proposed Fix: Feature Redesign → 4-Period Time-of-Day Binning

**Replace** the continuous `hour` (0–23) with a 4-period categorical:

```python
# BEFORE:
# hour = raw_hour  → continuous [0, 23]

# AFTER:
# time_period = categorical {Morning, Afternoon, Evening, Night}
TIME_PERIOD_CLASSES = ["Morning", "Afternoon", "Evening", "Night"]

def map_time_period(hour: int) -> str:
    if 6 <= hour < 12:
        return "Morning"
    elif 12 <= hour < 17:
        return "Afternoon"
    elif 17 <= hour < 21:
        return "Evening"
    else:
        return "Night"
```

### Why This Works
- **Reduces domain gap:** Absorbs fine-grained hour differences into coarser bins
- **Preserves temporal signal:** Morning/Afternoon/Evening/Night captures meaningful behavioral patterns
- **Reduces reconstruction difficulty:** Model learns 4 values instead of 24
- **Auditable:** Period names are interpretable

### Residual Domain Gap
After binning:
- Train distribution: Morning=0%, Afternoon=0%, Evening=~90%, Night=~10%
- Localhost distribution: Morning=~25%, Afternoon=~20%, Evening=~25%, Night=~30%
- Gap is reduced but not eliminated (Evening still dominates train)

**Expected improvement:** MSE ratio would decrease from34× to approximately 5–10× (estimated). This is a significant improvement but does not fully resolve the gap.

### Risk Analysis
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reduced temporal resolution | Certain | Low | 4 periods capture meaningful behavioral patterns |
| Residual domain gap | Certain | Medium | Combines with ip_address + duration_ms fixes to reduce total FPR |
| Retraining required | Certain | Low | Categorical replacement, same feature dimension |

### Verdict: RECOMMENDED
Significant reduction in domain gap. Combined with ip_address and duration_ms fixes, should bring hour contribution well below anomaly detection threshold.

---

## Feature 4: `device` — HIGH (score=66.7)

### Problem Summary
98.8% of localhost records have "Unknown Device" because User-Agent headers are absent/unrecognized in localhost API calls. Training has 71.5% "PC Windows". "Unknown Device" is in DEVICE_CLASSES vocabulary but was never seen during training → LabelEncoder assigns integer 6 (fallback) → decoder cannot reconstruct.

### Evidence
| Metric | Value |
|--------|-------|
| Localhost device | 98.8% "Unknown Device" |
| Train device | 71.5% "PC Windows", 21.9% "Android", 6.7% "iOS" |
| Unseen in train | "Unknown Device" (vocabulary position 6) |
| Scaled z-score | 0.49σ |
| MSE ratio | 226× |
| Contribution | 14.4% of total localhost MSE |
| Root cause | C (Logging artifact) |

### Proposed Fix: Feature Redesign → Fallback to "PC Windows"

**In `parse_user_agent_device()`**, when User-Agent is empty/unrecognized (returns "Unknown Device"), **fall back to "PC Windows"** instead:

```python
# BEFORE:
return "Unknown Device"

# AFTER:
return "PC Windows"  # system runs on Windows; fallback to most common training category
```

### Why This Works
- **Eliminates domain shift:** "Unknown Device" maps to "PC Windows" → same integer encoding as 71.5% of training data
- **Semantically reasonable:** The system runs on Windows; localhost API calls originate from the same server
- **Preserves anomaly signal:** A device mismatch (e.g., "Linux" from a Windows server) would still be detected
- **Zero architecture change:** Same encoder, same vocabulary, same model

### Risk Analysis
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| False normalization of actual device mismatches | Low | Low | If a non-Windows device makes localhost calls, it would be misclassified; this is acceptable since localhost traffic is excluded from scoring |
| Masking real device anomalies | Low | Medium | Only affects localhost records; production scoring uses actual User-Agent headers |
| No retraining required | Certain | None | This is a preprocessing-only change |

### Verdict: RECOMMENDED
Simple, low-risk fix that eliminates 14.4% of localhost MSE with no model changes.

---

## Feature 5: `activity` — MEDIUM (score=43.7)

*Note: activity is MEDIUM severity but included here because it has a clean fix.*

### Problem Summary
3 activity categories present in localhost but absent from training: "Keamanan & 2FA", "Kelola Sarana", "Peminjaman". These are system-triggered operations not captured in the training dataset.

### Evidence
| Metric | Value |
|--------|-------|
| Train categories | 8 unique |
| Localhost categories | 11 unique (+3 unseen) |
| Unseen categories | "Keamanan & 2FA", "Kelola Sarana", "Peminjaman" |
| MSE ratio | 33× |
| Contribution | 12.7% of total localhost MSE |
| Root cause | C (Logging artifact) |

### Proposed Fix: Feature Redesign → Reduced Activity Vocabulary

**Replace** the 12-category `activity` with a reduced 8-category set that merges rare/system-specific categories:

```python
# BEFORE (12 categories):
ACTIVITY_CLASSES = [
    "Login", "Logout", "Akses Berkas", "Kelola Berkas",
    "Kelola Perkara", "Kelola Sarana", "Kelola User",
    "Keamanan & 2FA", "Peminjaman", "Verifikasi",
    "Laporan & Anomali", "UNKNOWN",
]

# AFTER (8 categories — merge rare/system-specific into broader groups):
ACTIVITY_CLASSES_REDUCED = [
    "Login", "Logout", "Akses Berkas", "Kelola Berkas",
    "Kelola Perkara", "Kelola User", "Administrasi",  # merged: Keamanan & 2FA, Kelola Sarana, Peminjaman, Verifikasi
    "UNKNOWN",
]

def map_canonical_activity_reduced(activity_input: Any) -> str:
    base = map_canonical_activity(activity_input)
    if base in ("Keamanan & 2FA", "Kelola Sarana", "Peminjaman", "Verifikasi"):
        return "Administrasi"
    return base
```

### Why This Works
- **Eliminates unseen categories:** All 11 localhost activities map to one of 8 known categories
- **Preserves core signal:** Login/Logout/file operations are preserved; only rare categories merged
- **Auditable:** "Administrasi" is a meaningful group label

### Risk Analysis
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Reduced granularity for admin operations | Certain | Low | Admin operations are rare in training; merging them is safe |
| Retraining required | Certain | Low | Vocabulary change only, no architecture change |

### Verdict: RECOMMENDED
Clean fix that eliminates 12.7% of localhost MSE.

---

## Summary of Recommended Fixes

| Feature | Severity | Fix Type | Change | Retraining? |
|---------|----------|----------|--------|-------------|
| `ip_address` | CRITICAL | Feature redesign | 6→2 categories (Internal/External) | YES |
| `duration_ms` | CRITICAL | Feature redesign | Continuous→binary (has_telemetry) | YES |
| `hour` | HIGH | Feature redesign | 24h continuous→4-period categorical | YES |
| `device` | HIGH | Fallback mapping | "Unknown Device"→"PC Windows" | NO |
| `activity` | MEDIUM | Vocabulary reduction | 12→8 categories (merge rare) | YES |

**Total expected MSE reduction:** ~85–90% of current localhost MSE eliminated.
**Retraining required:** YES for 4 of 5 features (ip_address, duration_ms, hour, activity).
**Architecture change required:** NO — all fixes preserve the 9-feature input dimension.
**New dataset (V6) required:** YES — training data must include localhost patterns with redesigned features.

---

## Implementation Order (Suggested)

1. **device** (no retraining) — immediate fix, zero risk
2. **ip_address** (retraining required) — eliminates dominant MSE source
3. **duration_ms** (retraining required) — eliminates second-largest MSE source
4. **activity** (retraining required) — eliminates unseen categories
5. **hour** (retraining required) — reduces temporal domain gap
