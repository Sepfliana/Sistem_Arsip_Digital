"""Stage 7.7 — Device fallback mitigation inference + measurement.

NO retraining, NO production modification, NO threshold change.
All artifacts saved to mitigation/ directory only.
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np, pandas as pd, torch

B = Path(__file__).resolve().parents[3]
E = B / 'stage7' / 'experiment_v5'
MIT = E / 'mitigation'
MIT.mkdir(exist_ok=True)
sys.path.insert(0, str(B))
sys.path.insert(0, str(E))

from services.model_loader import VariationalAutoencoder
from utils.preprocessing_contract import (
    FEATURE_COLUMNS, map_canonical_activity, map_canonical_status,
    parse_user_agent_device, map_ip_category,
    transform_numeric_features, parse_timestamp_wib,
)
from mitigation.device_fallback import apply_device_fallback, get_device_stats

F = list(FEATURE_COLUMNS)
ENC_F = ['activity', 'status', 'device', 'ip_address']
VAL_THR = 0.13773
PROD_THR = 3.1496

print("[1/7] Loading artifacts...")
with (E / 'label_encoders_v5_experiment.pkl').open('rb') as f:
    enc = pickle.load(f)
with (E / 'scaler_v5_experiment.pkl').open('rb') as f:
    sc = pickle.load(f)

print("[2/7] Loading data...")
te = pd.read_csv(E / 'test_normal_manifest.csv')
ava = pd.read_csv(E / 'validation_anomaly_manifest.csv')
ate = pd.read_csv(E / 'test_anomaly_manifest.csv')
raw = pd.read_csv(B / 'dataset/retraining/retraining_dataset_combined_raw.csv',
                  encoding='utf-8-sig',
                  usecols=['source_type','user_id','aksi','status','device',
                           'ip_address','durasi_ms','jumlah_objek','waktu'])
lh = raw[raw.source_type == 'REAL_DB'].copy()
del raw
print(f"  test_normal={len(te)} val_anomaly={len(ava)} test_anomaly={len(ate)} localhost={len(lh)}")

def bulk_canon(df, fix_device=False):
    rows = []
    for _, r in df.iterrows():
        uid, dur, obj = transform_numeric_features(
            r.get('user_id', 1), r.get('durasi_ms', r.get('duration_ms', 0)),
            r.get('jumlah_objek', r.get('object_count', 0)))
        h, d = parse_timestamp_wib(r.get('waktu', r.get('timestamp', '')))
        dev = parse_user_agent_device(r.get('device', ''))
        if fix_device:
            dev = apply_device_fallback({'device': dev})['device']
        rows.append({
            'user_id': uid, 'activity': map_canonical_activity(r.get('aksi', r.get('activity', ''))),
            'status': map_canonical_status(r.get('status', '')), 'device': dev,
            'ip_address': map_ip_category(r.get('ip_address', '')),
            'duration_ms': dur, 'object_count': obj, 'hour': h, 'day_of_week': d,
        })
    return pd.DataFrame(rows)

def xform(df, fix_device=False):
    c = bulk_canon(df, fix_device=fix_device)
    x = np.column_stack([
        c.user_id.astype(float),
        *[enc[k].transform(c[k]).astype(float) for k in ENC_F],
        *[c[k].astype(float) for k in ['duration_ms', 'object_count', 'hour', 'day_of_week']]
    ])
    return c, sc.transform(x).astype('float32')

groups = {'test_normal': te, 'validation_anomaly': ava, 'test_anomaly': ate, 'localhost': lh}

print("[3/7] Transforming BEFORE + AFTER...")
Xb, Xa = {}, {}
Cb, Ca = {}, {}
for nm, df in groups.items():
    cb, xb = xform(df, fix_device=False)
    ca, xa = xform(df, fix_device=True)
    Xb[nm], Xa[nm] = xb, xa
    Cb[nm], Ca[nm] = cb, ca
    print(f"  {nm} done")

print("[4/7] Device stats...")
for nm in groups:
    st = get_device_stats(groups[nm].to_dict('records'), label=nm)
    print(f"  {nm}: {st['changed']}/{st['total']} changed ({st['change_pct']}%)")

print("[5/7] Loading model + forward pass...")
m = VariationalAutoencoder()
m.load_state_dict(torch.load(E / 'retraining/vae_model_v5_experiment.pth',
                             map_location='cpu', weights_only=False))
m.eval()

def fwd(X):
    with torch.no_grad():
        q = torch.from_numpy(X).float()
        r, mu, lv = m(q)
        return r.detach().numpy(), mu.detach().numpy(), lv.detach().numpy()

MSE = {}
for nm in groups:
    Rb, _, _ = fwd(Xb[nm])
    Ra, _, _ = fwd(Xa[nm])
    MSE[f'{nm}_before'] = np.mean((Xb[nm] - Rb) ** 2, axis=1)
    MSE[f'{nm}_after'] = np.mean((Xa[nm] - Ra) ** 2, axis=1)
    print(f"  {nm}: before={MSE[f'{nm}_before'].mean():.6f} after={MSE[f'{nm}_after'].mean():.6f}")

# ─── TASK 3: Measure impact ──────────────────────────────────────────────────
def metrics(mse, thr):
    n = len(mse)
    fp = int(np.sum(mse > thr))
    return {
        'n': n, 'mean': float(mse.mean()), 'median': float(np.median(mse)),
        'p5': float(np.percentile(mse, 5)), 'p95': float(np.percentile(mse, 95)),
        'p99': float(np.percentile(mse, 99)),
        'min': float(mse.min()), 'max': float(mse.max()),
        'fp_count': fp, 'fpr': round(fp / n, 6),
    }

print("[6/7] Computing metrics...")
rows = []
for nm in groups:
    for phase in ['before', 'after']:
        key = f'{nm}_{phase}'
        m = metrics(MSE[key], VAL_THR)
        mp = metrics(MSE[key], PROD_THR)
        rows.append({
            'group': nm, 'phase': phase, 'threshold': 'validation',
            **m, 'fpr_prod': mp['fpr'], 'fp_prod': mp['fp_count'],
        })

# Save per-group metrics
pd.DataFrame(rows).to_csv(MIT / 'mse_after_device_fallback.csv', index=False)

# ─── TASK 4: BEFORE vs AFTER comparison ──────────────────────────────────────
print("[7/7] Comparison table...")
comp_rows = []
for nm in groups:
    mb = MSE[f'{nm}_before']
    ma = MSE[f'{nm}_after']
    delta_mse = float(ma.mean() - mb.mean())
    fp_b_v = int(np.sum(mb > VAL_THR))
    fp_a_v = int(np.sum(ma > VAL_THR))
    fp_b_p = int(np.sum(mb > PROD_THR))
    fp_a_p = int(np.sum(ma > PROD_THR))
    comp_rows.extend([
        {'metric': f'{nm}_mean_mse', 'before': round(float(mb.mean()), 6),
         'after': round(float(ma.mean()), 6), 'delta': round(delta_mse, 6),
         'delta_pct': round(delta_mse / max(float(mb.mean()), 1e-12) * 100, 2)},
        {'metric': f'{nm}_p95_mse', 'before': round(float(np.percentile(mb, 95)), 6),
         'after': round(float(np.percentile(ma, 95)), 6),
         'delta': round(float(np.percentile(ma, 95) - np.percentile(mb, 95)), 6)},
        {'metric': f'{nm}_fp_val_thr', 'before': fp_b_v, 'after': fp_a_v,
         'delta': fp_a_v - fp_b_v},
        {'metric': f'{nm}_fpr_val_thr', 'before': round(fp_b_v / len(mb), 4),
         'after': round(fp_a_v / len(ma), 4),
         'delta': round((fp_a_v - fp_b_v) / len(mb), 4)},
        {'metric': f'{nm}_fp_prod_thr', 'before': fp_b_p, 'after': fp_a_p,
         'delta': fp_a_p - fp_b_p},
        {'metric': f'{nm}_fpr_prod_thr', 'before': round(fp_b_p / len(mb), 4),
         'after': round(fp_a_p / len(ma), 4),
         'delta': round((fp_a_p - fp_b_p) / len(mb), 4)},
    ])

pd.DataFrame(comp_rows).to_csv(MIT / 'device_fallback_impact.csv', index=False)

# ─── Print summary ───────────────────────────────────────────────────────────
print("\n" + "=" * 90)
print("DEVICE FALLBACK IMPACT SUMMARY")
print("=" * 90)
for nm in groups:
    mb = MSE[f'{nm}_before']
    ma = MSE[f'{nm}_after']
    fp_bv = int(np.sum(mb > VAL_THR))
    fp_av = int(np.sum(ma > VAL_THR))
    fp_bp = int(np.sum(mb > PROD_THR))
    fp_ap = int(np.sum(ma > PROD_THR))
    print(f"\n  {nm} (n={len(mb)}):")
    print(f"    Mean MSE:  {mb.mean():.6f} -> {ma.mean():.6f}  ({(ma.mean()-mb.mean())/max(mb.mean(),1e-12)*100:+.1f}%)")
    print(f"    FP (val):  {fp_bv}/{len(mb)} -> {fp_av}/{len(mb)}  ({fp_bv - fp_av} reduction)")
    print(f"    FP (prod): {fp_bp}/{len(mb)} -> {fp_ap}/{len(mb)}  ({fp_bp - fp_ap} reduction)")

# ─── TASK 5: Validate assumption ─────────────────────────────────────────────
lh_before_fp = int(np.sum(MSE['localhost_before'] > VAL_THR))
lh_after_fp = int(np.sum(MSE['localhost_after'] > VAL_THR))
lh_reduction = lh_before_fp - lh_after_fp
lh_fpr_before = lh_before_fp / len(MSE['localhost_before'])
lh_fpr_after = lh_after_fp / len(MSE['localhost_after'])

# Check anomaly recall stability
ava_before_correct = int(np.sum(MSE['validation_anomaly_before'] > VAL_THR))
ava_after_correct = int(np.sum(MSE['validation_anomaly_after'] > VAL_THR))
ate_before_correct = int(np.sum(MSE['test_anomaly_before'] > VAL_THR))
ate_after_correct = int(np.sum(MSE['test_anomaly_after'] > VAL_THR))

sig_reduce = lh_reduction > 10  # >10 records reduction = significant
preserve_detection = (ava_before_correct == ava_after_correct) and (ate_before_correct == ate_after_correct)

single_sufficient = sig_reduce and (lh_fpr_after < 0.05)

verdict = {
    "single_feature_sufficient": single_sufficient,
    "fpr_significantly_reduced": sig_reduce,
    "fpr_before": round(lh_fpr_before, 4),
    "fpr_after": round(lh_fpr_after, 4),
    "records_reduced": lh_reduction,
    "anomaly_detection_preserved": preserve_detection,
    "ava_recall_before": round(ava_before_correct / len(MSE['validation_anomaly_before']), 4),
    "ava_recall_after": round(ava_after_correct / len(MSE['validation_anomaly_after']), 4),
    "ate_recall_before": round(ate_before_correct / len(MSE['test_anomaly_before']), 4),
    "ate_recall_after": round(ate_after_correct / len(MSE['test_anomaly_after']), 4),
    "conclusion": "MULTI_FEATURE_REDESIGN_REQUIRED" if not single_sufficient else "DEVICE_FIX_SUFFICIENT",
}

with (MIT / 'single_feature_validation.json').open('w') as f:
    json.dump(verdict, f, indent=2)

print("\n" + "=" * 90)
print("SINGLE-FEATURE VALIDATION")
print("=" * 90)
print(f"  Localhost FPR:  {lh_fpr_before:.4f} -> {lh_fpr_after:.4f}  (reduction: {lh_reduction} records)")
print(f"  Significant reduction (>10 records): {sig_reduce}")
print(f"  Anomaly detection preserved: {preserve_detection}")
print(f"  Single-feature sufficient: {single_sufficient}")
print(f"  CONCLUSION: {verdict['conclusion']}")
print(f"\nAll outputs saved to {MIT}")
