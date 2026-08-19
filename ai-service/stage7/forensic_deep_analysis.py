"""Deep forensic analysis: per-feature MSE, latent space, KL. Optimized for speed."""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np, pandas as pd, torch
B = Path(__file__).resolve().parents[1]
E = B / 'stage7' / 'experiment_v5'
sys.path.insert(0, str(B))
from services.model_loader import VariationalAutoencoder
from utils.preprocessing_contract import (
    FEATURE_COLUMNS, map_canonical_activity, map_canonical_status,
    parse_user_agent_device, map_ip_category, transform_numeric_features, parse_timestamp_wib
)

F = list(FEATURE_COLUMNS)

def bulk_canon(df):
    """Vectorized canonical transform — avoids per-row process_record call."""
    uids, durs, objs, hours, dows = [], [], [], [], []
    for _, r in df.iterrows():
        uid, dur, obj = transform_numeric_features(
            r.get('user_id', 1), r.get('durasi_ms', r.get('duration_ms', 0)), r.get('jumlah_objek', r.get('object_count', 0))
        )
        h, d = parse_timestamp_wib(r.get('waktu', r.get('timestamp', '')))
        uids.append(uid); durs.append(dur); objs.append(obj); hours.append(h); dows.append(d)
    out = pd.DataFrame({
        'user_id': uids,
        'activity': [map_canonical_activity(r.get('aksi', r.get('activity', ''))) for _, r in df.iterrows()],
        'status': [map_canonical_status(r.get('status', '')) for _, r in df.iterrows()],
        'device': [parse_user_agent_device(r.get('device', '')) for _, r in df.iterrows()],
        'ip_address': [map_ip_category(r.get('ip_address', '')) for _, r in df.iterrows()],
        'duration_ms': durs,
        'object_count': objs,
        'hour': hours,
        'day_of_week': dows,
    })
    return out

# ─── Load artifacts ──────────────────────────────────────────────────────────
with (E / 'label_encoders_v5_experiment.pkl').open('rb') as f:
    enc = pickle.load(f)
with (E / 'scaler_v5_experiment.pkl').open('rb') as f:
    sc = pickle.load(f)

# Load manifests
tr = pd.read_csv(E / 'train_normal_manifest.csv')
va = pd.read_csv(E / 'validation_normal_manifest.csv')
te = pd.read_csv(E / 'test_normal_manifest.csv')
ava = pd.read_csv(E / 'validation_anomaly_manifest.csv')
ate = pd.read_csv(E / 'test_anomaly_manifest.csv')

# Load only localhost from combined raw
print("Loading localhost data...")
raw = pd.read_csv(B / 'dataset/retraining/retraining_dataset_combined_raw.csv', encoding='utf-8-sig', usecols=['source_type','user_id','aksi','status','device','ip_address','durasi_ms','jumlah_objek','waktu'])
lh = raw[raw.source_type == 'REAL_DB'].copy()
del raw
print(f"  localhost: {len(lh)} rows")

def xform(d):
    c = bulk_canon(d)
    x = np.column_stack([
        c.user_id.astype(float),
        *[enc[k].transform(c[k]).astype(float) for k in ['activity', 'status', 'device', 'ip_address']],
        *[c[k].astype(float) for k in ['duration_ms', 'object_count', 'hour', 'day_of_week']]
    ])
    return c, sc.transform(x).astype('float32')

print("Transforming groups...")
c_tr, X_tr = xform(tr); print("  train done")
c_va, X_va = xform(va); print("  val done")
c_te, X_te = xform(te); print("  test done")
c_ava, X_ava = xform(ava); print("  val_anom done")
c_ate, X_ate = xform(ate); print("  test_anom done")
c_lh, X_lh = xform(lh); print("  localhost done")

# ─── Load model ─────────────────────────────────────────────────────────────
print("Loading model...")
m = VariationalAutoencoder()
m.load_state_dict(torch.load(E / 'retraining/vae_model_v5_experiment.pth', map_location='cpu', weights_only=False))
m.eval()

# ─── Forward pass ────────────────────────────────────────────────────────────
print("Running forward passes...")
torch.manual_seed(42)
with torch.no_grad():
    def fwd(X):
        q = torch.from_numpy(X).float()
        recon, mu, logvar = m(q)
        return recon.detach().numpy(), mu.detach().numpy(), logvar.detach().numpy()

R_tr, mu_tr, lv_tr = fwd(X_tr)
R_te, mu_te, lv_te = fwd(X_te)
R_ava, mu_ava, lv_ava = fwd(X_ava)
R_lh, mu_lh, lv_lh = fwd(X_lh)
print("  forward passes done")

# ─── Per-feature MSE decomposition ──────────────────────────────────────────
mse_tr = (X_tr - R_tr) ** 2
mse_te = (X_te - R_te) ** 2
mse_lh = (X_lh - R_lh) ** 2
mse_ava = (X_ava - R_ava) ** 2

feat_mse = []
for i, k in enumerate(F):
    feat_mse.append({
        'feature': k,
        'train_mean_mse': float(mse_tr[:, i].mean()),
        'train_median_mse': float(np.median(mse_tr[:, i])),
        'train_p95_mse': float(np.percentile(mse_tr[:, i], 95)),
        'train_p99_mse': float(np.percentile(mse_tr[:, i], 99)),
        'localhost_mean_mse': float(mse_lh[:, i].mean()),
        'localhost_median_mse': float(np.median(mse_lh[:, i])),
        'localhost_p5_mse': float(np.percentile(mse_lh[:, i], 5)),
        'localhost_p95_mse': float(np.percentile(mse_lh[:, i], 95)),
        'localhost_to_train_ratio': float(mse_lh[:, i].mean() / max(mse_tr[:, i].mean(), 1e-12)),
        'localhost_contribution_pct': float(mse_lh[:, i].mean() / max(mse_lh.mean(), 1e-12) * 100),
        'train_contribution_pct': float(mse_tr[:, i].mean() / max(mse_tr.mean(), 1e-12) * 100),
        'anomaly_mean_mse': float(mse_ava[:, i].mean()),
        'anomaly_to_train_ratio': float(mse_ava[:, i].mean() / max(mse_tr[:, i].mean(), 1e-12)),
    })
pd.DataFrame(feat_mse).to_csv(E / 'forensic' / 'per_feature_mse_decomposition.csv', index=False)

# ─── Latent space analysis ──────────────────────────────────────────────────
latent = []
for name, mu_arr, lv_arr in [
    ('train_normal', mu_tr, lv_tr),
    ('test_normal', mu_te, lv_te),
    ('validation_anomaly', mu_ava, lv_ava),
    ('localhost', mu_lh, lv_lh),
]:
    sigma2 = np.exp(lv_arr)
    d = {'group': name, 'n': len(mu_arr)}
    for i in range(8):
        d[f'mu_dim{i}_mean'] = float(mu_arr[:, i].mean())
        d[f'mu_dim{i}_std'] = float(mu_arr[:, i].std())
        d[f'var_dim{i}_mean'] = float(sigma2[:, i].mean())
    d['mu_l2_mean'] = float(np.linalg.norm(mu_arr, axis=1).mean())
    d['mu_l2_std'] = float(np.linalg.norm(mu_arr, axis=1).std())
    d['var_l2_mean'] = float(np.linalg.norm(sigma2, axis=1).mean())
    d['mu_center_l2'] = float(np.linalg.norm(mu_arr.mean(axis=0)))
    latent.append(d)
pd.DataFrame(latent).to_csv(E / 'forensic' / 'latent_space_analysis.csv', index=False)

# ─── KL divergence ──────────────────────────────────────────────────────────
def kl_per_sample(mu, logvar):
    return -0.5 * np.sum(1 + logvar - mu**2 - np.exp(logvar), axis=1)

kl_tr = kl_per_sample(mu_tr, lv_tr)
kl_te = kl_per_sample(mu_te, lv_te)
kl_lh = kl_per_sample(mu_lh, lv_lh)
kl_ava = kl_per_sample(mu_ava, lv_ava)

kl_data = []
for name, kl_arr in [('train_normal', kl_tr), ('test_normal', kl_te), ('localhost', kl_lh), ('validation_anomaly', kl_ava)]:
    kl_data.append({'group': name, 'kl_mean': float(kl_arr.mean()), 'kl_median': float(np.median(kl_arr)),
                     'kl_std': float(kl_arr.std()), 'kl_min': float(kl_arr.min()), 'kl_max': float(kl_arr.max()),
                     'kl_p5': float(np.percentile(kl_arr, 5)), 'kl_p95': float(np.percentile(kl_arr, 95))})
pd.DataFrame(kl_data).to_csv(E / 'forensic' / 'kl_divergence_analysis.csv', index=False)

# ─── Per-dimension mu comparison ─────────────────────────────────────────────
dim_compare = []
for i in range(8):
    dim_compare.append({
        'dim': i,
        'train_mu_mean': float(mu_tr[:, i].mean()),
        'train_mu_std': float(mu_tr[:, i].std()),
        'localhost_mu_mean': float(mu_lh[:, i].mean()),
        'localhost_mu_std': float(mu_lh[:, i].std()),
        'anomaly_mu_mean': float(mu_ava[:, i].mean()),
        'anomaly_mu_std': float(mu_ava[:, i].std()),
        'mu_shift_lh_vs_train': float(abs(mu_lh[:, i].mean() - mu_tr[:, i].mean())),
        'mu_shift_anom_vs_train': float(abs(mu_ava[:, i].mean() - mu_tr[:, i].mean())),
        'ratio_shift': float(abs(mu_lh[:, i].mean() - mu_tr[:, i].mean()) / max(abs(mu_ava[:, i].mean() - mu_tr[:, i].mean()), 1e-12)),
        'var_train': float(np.exp(lv_tr[:, i]).mean()),
        'var_localhost': float(np.exp(lv_lh[:, i]).mean()),
        'var_anomaly': float(np.exp(lv_ava[:, i]).mean()),
    })
pd.DataFrame(dim_compare).to_csv(E / 'forensic' / 'latent_mu_dimension_comparison.csv', index=False)

# ─── Scaled feature comparison ──────────────────────────────────────────────
scaled_comp = []
for i, k in enumerate(F):
    scaled_comp.append({
        'feature': k,
        'train_scaled_mean': float(X_tr[:, i].mean()),
        'train_scaled_std': float(X_tr[:, i].std()),
        'localhost_scaled_mean': float(X_lh[:, i].mean()),
        'localhost_scaled_std': float(X_lh[:, i].std()),
        'anomaly_scaled_mean': float(X_ava[:, i].mean()),
        'abs_z_localhost': float(abs(X_lh[:, i].mean() - X_tr[:, i].mean()) / max(X_tr[:, i].std(), 1e-12)),
        'abs_z_anomaly': float(abs(X_ava[:, i].mean() - X_tr[:, i].mean()) / max(X_tr[:, i].std(), 1e-12)),
    })
pd.DataFrame(scaled_comp).to_csv(E / 'forensic' / 'scaled_feature_comparison.csv', index=False)

# ─── Print summary ──────────────────────────────────────────────────────────
print()
print('=' * 80)
print('PER-FEATURE MSE DECOMPOSITION')
print('=' * 80)
for row in sorted(feat_mse, key=lambda x: x['localhost_to_train_ratio'], reverse=True):
    print(f"  {row['feature']:15s}  train={row['train_mean_mse']:.6f}  localhost={row['localhost_mean_mse']:.6f}  "
          f"ratio={row['localhost_to_train_ratio']:.1f}x  contrib={row['localhost_contribution_pct']:.1f}%")

print()
print('=' * 80)
print('KL DIVERGENCE')
print('=' * 80)
for row in kl_data:
    print(f"  {row['group']:25s}  KL_mean={row['kl_mean']:.4f}  KL_median={row['kl_median']:.4f}")

print()
print('=' * 80)
print('LATENT SPACE CENTROID DISTANCES')
print('=' * 80)
ct = mu_tr.mean(axis=0)
c_an = mu_ava.mean(axis=0)
c_lh = mu_lh.mean(axis=0)
print(f"  train-anomaly:     {np.linalg.norm(ct - c_an):.6f}")
print(f"  train-localhost:   {np.linalg.norm(ct - c_lh):.6f}")
print(f"  localhost-anomaly: {np.linalg.norm(c_lh - c_an):.6f}")
print(f"  localhost-train / anomaly-train = {np.linalg.norm(c_lh - ct) / max(np.linalg.norm(c_an - ct), 1e-12):.2f}")

print()
print('=' * 80)
print('TOP LOCALHOST-SHIFTED LATENT DIMENSIONS')
print('=' * 80)
for row in sorted(dim_compare, key=lambda x: x['mu_shift_lh_vs_train'], reverse=True):
    print(f"  dim {row['dim']}:  shift_lh={row['mu_shift_lh_vs_train']:.4f}  shift_anom={row['mu_shift_anom_vs_train']:.4f}  "
          f"ratio={row['ratio_shift']:.2f}x  var_train={row['var_train']:.4f}  var_lh={row['var_localhost']:.4f}")

print()
print('=' * 80)
print('SCALED ABSOLUTE Z-SCORES')
print('=' * 80)
for row in sorted(scaled_comp, key=lambda x: x['abs_z_localhost'], reverse=True):
    print(f"  {row['feature']:15s}  |z|_localhost={row['abs_z_localhost']:.3f}  |z|_anomaly={row['abs_z_anomaly']:.3f}")

train_total_mse = mse_tr.mean(axis=1)
lh_total_mse = mse_lh.mean(axis=1)
print()
print('=' * 80)
print('MSE OVERLAP ANALYSIS')
print('=' * 80)
print(f"  Train  MSE: min={train_total_mse.min():.6f} mean={train_total_mse.mean():.6f} p99={np.percentile(train_total_mse, 99):.6f} max={train_total_mse.max():.6f}")
print(f"  Lh     MSE: min={lh_total_mse.min():.6f} mean={lh_total_mse.mean():.6f} p5={np.percentile(lh_total_mse, 5):.6f} max={lh_total_mse.max():.6f}")
print(f"  Localhost min MSE > Train max MSE: {lh_total_mse.min() > train_total_mse.max()}")
print(f"  Separation gap: {lh_total_mse.min() - train_total_mse.max():.6f}")

print(f"\nAll CSVs saved to {E / 'forensic'}")
print("DONE")
