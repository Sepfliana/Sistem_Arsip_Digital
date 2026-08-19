"""Device fallback mitigation layer — EXPERIMENTAL, ISOLATED, REVERSIBLE.

Maps unseen device categories to the dominant training category ("PC Windows").
Does NOT modify original encoders, scaler, or model.

Usage:
    from mitigation.device_fallback import apply_device_fallback, get_device_stats
"""
from __future__ import annotations
from typing import Any, Dict, List
from utils.preprocessing_contract import DEVICE_CLASSES

# Dominant training category (71.5% of TRAIN_NORMAL)
SAFE_DEVICE = "PC Windows"

# Training-seen categories (will NOT be remapped)
TRAIN_SEEN_DEVICES = {"PC Windows", "Android", "iOS"}


def apply_device_fallback(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of record with device remapped if unseen in training.

    Rules:
    - device ∈ {"PC Windows", "Android", "iOS"} → keep original (seen in training)
    - device ∈ {"Unknown Device", "MacOS", "Linux", "Virtual Machine", other} → map to SAFE_DEVICE
    - Empty/missing device → map to SAFE_DEVICE

    Does NOT mutate the original record.
    """
    out = dict(record)
    dev = out.get("device", "")
    if not dev:
        out["device"] = SAFE_DEVICE
        return out

    dev_str = str(dev).strip()
    if dev_str in TRAIN_SEEN_DEVICES:
        return out  # keep original

    # Remap unseen/unknown to safe training category
    out["device"] = SAFE_DEVICE
    return out


def apply_device_fallback_bulk(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply device fallback to a list of records. Returns new list."""
    return [apply_device_fallback(r) for r in records]


def get_device_stats(records: List[Dict[str, Any]], label: str = "") -> Dict[str, Any]:
    """Compute before/after device category distribution."""
    from collections import Counter
    before = Counter()
    after = Counter()
    changed = 0
    for r in records:
        original = str(r.get("device", "")).strip()
        remapped = apply_device_fallback(r)["device"]
        before[original] += 1
        after[remapped] += 1
        if original != remapped:
            changed += 1
    return {
        "label": label,
        "total": len(records),
        "changed": changed,
        "change_pct": round(changed / max(len(records), 1) * 100, 2),
        "before_dist": dict(before.most_common()),
        "after_dist": dict(after.most_common()),
    }
