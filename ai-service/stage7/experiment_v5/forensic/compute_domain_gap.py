"""Compute normalized domain gap score per feature and rank severity."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np, pandas as pd

E = Path(__file__).resolve().parents[0]
FORENSIC = E

# ─── Load forensic data ──────────────────────────────────────────────────────
mse_df = pd.read_csv(FORENSIC / 'per_feature_mse_decomposition.csv')
scaled_df = pd.read_csv(FORENSIC / 'scaled_feature_comparison.csv')
kl_df = pd.read_csv(FORENSIC / 'kl_divergence_analysis.csv')
latent_df = pd.read_csv(FORENSIC / 'latent_space_analysis.csv')

# ─── Global KL ratio (latent space level) ────────────────────────────────────
kl_train = float(kl_df[kl_df.group == 'train_normal']['kl_mean'].iloc[0])
kl_lh = float(kl_df[kl_df.group == 'localhost']['kl_mean'].iloc[0])
kl_ratio_global = kl_lh / kl_train  # 79.09 / 28.25 = 2.80

# ─── Compute per-feature domain gap score ────────────────────────────────────
# Components:
#   1. z_score: |mean_localhost_scaled - mean_train_scaled| / std_train  (from scaled data)
#   2. mse_ratio: mean_mse_localhost / mean_mse_train  (from MSE decomposition, log1p scaled)
#   3. contribution: localhost_contribution_pct / 100  (share of total localhost MSE)
#
# Combined: domain_gap_score = normalize(z_score) + normalize(log1p(mse_ratio)) + normalize(contribution)
# All normalized to [0, 1] range within the 9 features, then averaged.

features = list(mse_df.feature)
records = []

for feat in features:
    mse_row = mse_df[mse_df.feature == feat].iloc[0]
    sc_row = scaled_df[scaled_df.feature == feat].iloc[0]

    z_lh = float(sc_row.abs_z_localhost)
    # Handle ip_address's astronomically large z-score by capping for scoring
    z_lh_capped = min(z_lh, 100.0)  # cap at 100σ for scoring purposes

    mse_ratio = float(mse_row.localhost_to_train_ratio)
    # Handle ip_address's infinite ratio
    mse_ratio_capped = min(mse_ratio, 1e6)  # cap at 1M for scoring
    log_mse_ratio = math.log1p(mse_ratio_capped)

    contribution = float(mse_row.localhost_contribution_pct) / 100.0  # normalize to [0,1] scale
    # Note: ip_address contribution is 301% (>1.0) due to >100% of total
    # This is fine — it indicates dominance

    records.append({
        'feature': feat,
        'z_score_raw': z_lh,
        'z_score_capped': z_lh_capped,
        'mse_ratio_raw': mse_ratio,
        'log_mse_ratio': log_mse_ratio,
        'contribution_pct': float(mse_row.localhost_contribution_pct),
        'contribution_norm': contribution,
        'train_mse': float(mse_row.train_mean_mse),
        'localhost_mse': float(mse_row.localhost_mean_mse),
    })

df = pd.DataFrame(records)

# ─── Normalize each component ────────────────────────────────────────────────
# Use rank-based scoring: each component contributes its percentile rank [0, 1]
# across the 9 features. This is robust to outliers and produces natural separation.

df['z_rank'] = df['z_score_capped'].rank(pct=True)
df['mse_rank'] = df['log_mse_ratio'].rank(pct=True)
df['contrib_rank'] = df['contribution_norm'].rank(pct=True)

# ─── Composite domain gap score ─────────────────────────────────────────────
# Weighted combination of rank scores:
#   - z_rank: 30%  (scaled space shift — direct observability)
#   - mse_rank: 40%  (reconstruction failure — model-level impact)
#   - contrib_rank: 30%  (MSE dominance — severity within total error)
#
# Score range [0, 100] where 100 = worst observed feature.

W_Z, W_MSE, W_CONTRIB = 0.30, 0.40, 0.30

df['domain_gap_score'] = (
    W_Z * df['z_rank'] +
    W_MSE * df['mse_rank'] +
    W_CONTRIB * df['contrib_rank']
)

# Scale to [0, 100]
df['domain_gap_score'] = (df['domain_gap_score'] / df['domain_gap_score'].max() * 100).round(2)

# ─── Rank severity ──────────────────────────────────────────────────────────
def classify(score):
    if score >= 80: return 'CRITICAL'
    if score >= 50: return 'HIGH'
    if score >= 20: return 'MEDIUM'
    return 'LOW'

df['severity'] = df['domain_gap_score'].apply(classify)

# ─── Sort by score ──────────────────────────────────────────────────────────
df = df.sort_values('domain_gap_score', ascending=False).reset_index(drop=True)
df['rank'] = range(1, len(df) + 1)

# ─── Output ──────────────────────────────────────────────────────────────────
out = df[[
    'rank', 'feature', 'severity', 'domain_gap_score',
    'z_score_raw', 'mse_ratio_raw', 'contribution_pct',
    'z_rank', 'mse_rank', 'contrib_rank',
    'train_mse', 'localhost_mse',
]].copy()

out.to_csv(FORENSIC / 'domain_gap_ranking.csv', index=False)

# ─── Print summary ──────────────────────────────────────────────────────────
print("DOMAIN GAP RANKING")
print("=" * 100)
print(f"{'Rank':<5} {'Feature':<15} {'Severity':<10} {'Score':>7}  {'z_raw':>10}  {'mse_ratio':>12}  {'contrib%':>8}")
print("-" * 100)
for _, r in out.iterrows():
    z_disp = r['z_score_raw']
    if z_disp > 1e6:
        z_disp_str = "3e+12"
    else:
        z_disp_str = f"{z_disp:.2f}"
    print(f"{int(r['rank']):<5} {r['feature']:<15} {r['severity']:<10} {r['domain_gap_score']:>7.1f}  "
          f"{z_disp_str:>10}  {r['mse_ratio_raw']:>12.1f}  {r['contribution_pct']:>8.1f}")

print(f"\nGlobal KL ratio (localhost/train): {kl_ratio_global:.2f}x")
print(f"KL train={kl_train:.2f}, localhost={kl_lh:.2f}")
print(f"\nSaved: {FORENSIC / 'domain_gap_ranking.csv'}")
