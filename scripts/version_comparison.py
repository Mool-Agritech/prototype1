"""
version_comparison.py
──────────────────────
Recomputes v5, v6, v7/v8 (CHF composite), and v9 (DI/FI) trigger logic —
using their ACTUAL published logic — against the SAME 22-year dataset
(2003-2024) and SAME PMFBY benchmark window (2018-2024), for a true
apples-to-apples comparison. No hand-waved percentages.

Output: data/processed/version_comparison_metrics.csv
        vidarbha_outputs/v9_version_comparison.png
"""
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr
import matplotlib.pyplot as plt

OUT = Path('./vidarbha_outputs')
OUT.mkdir(exist_ok=True)

BACKTEST_YEARS = list(range(2003, 2025))
PMFBY_YEARS = list(range(2018, 2025))
PMFBY_LOSS_THRESHOLD = 0.10
SUM_INSURED_PER_HA = 40000

DISTRICT_LPA = {'Yavatmal': 950.0, 'Amravati': 850.0, 'Chandrapur': 1100.0, 'Wardha': 860.0}

df = pd.read_csv('data/processed/all_districts_23yr_features.csv')
df['revenue_circle'] = df['revenue_circle'].str.strip()
bt = df[df['year'].isin(BACKTEST_YEARS)].copy()
bt['pmfby_stress'] = bt['rate_total'] > PMFBY_LOSS_THRESHOLD

apy_raw = pd.read_csv('data/processed/apy_district_yields_v2.csv')
apy_raw = apy_raw.dropna(subset=['cotton_lint_yield_kg_ha', 'soybean_yield_kg_ha'], how='all')
crop_yield_cols = [c for c in apy_raw.columns if c.endswith('_yield_kg_ha')]
for crop_col in crop_yield_cols:
    z_col = crop_col.replace('_yield_kg_ha', '_z')
    for dist in apy_raw['district'].unique():
        full = apy_raw[apy_raw['district'] == dist][crop_col].dropna()
        mu, sigma = full.mean(), full.std()
        mask = apy_raw['district'] == dist
        apy_raw.loc[mask, z_col] = (apy_raw.loc[mask, crop_col] - mu) / sigma if sigma > 0 else 0
z_cols = [c for c in apy_raw.columns if c.endswith('_z')]
apy_raw['crop_stress_z'] = apy_raw[z_cols].mean(axis=1)


def metrics_for(d, trigger_col, pmfby_col='trigger_any_pmfby'):
    """Compute fire rate, PMFBY precision/recall/F1, basis risk (2018-2024)."""
    pm = d[d['year'].isin(PMFBY_YEARS) & d['rate_total'].notna()]
    fire_rate = d[trigger_col].mean()

    tp = (pm[trigger_col] & pm['pmfby_stress']).sum()
    fp = (pm[trigger_col] & ~pm['pmfby_stress']).sum()
    fn = (~pm[trigger_col] & pm['pmfby_stress']).sum()
    tn = (~pm[trigger_col] & ~pm['pmfby_stress']).sum()
    total = len(pm)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    basis_risk = fn / total if total > 0 else 0

    # APY correlation (district-year)
    dy = d.groupby(['district', 'year'])[trigger_col].mean().reset_index()
    dy = dy.merge(apy_raw[['district', 'year', 'crop_stress_z']], on=['district', 'year'], how='inner')
    apy_rho = np.nan
    if len(dy) > 10 and dy[trigger_col].std() > 0:
        apy_rho, _ = spearmanr(dy[trigger_col], dy['crop_stress_z'])

    return {
        'fire_rate_22yr': fire_rate, 'precision': precision, 'recall': recall,
        'f1': f1, 'basis_risk': basis_risk, 'n_pmfby_obs': total,
        'apy_trigger_corr': apy_rho,
    }


results = {}

# ══════════════════════════ v5: 2-of-3 AND (no heat, no SMAP) ══════════════
DROUGHT_RULES_V5 = [('VHI_mean', 'low'), ('drySpellDays', 'high'), ('dry_spell_julaug', 'high')]
FLOOD_RULES = [('cumRain_mm', 'high'), ('heavy_rain_days', 'high'), ('sm_wet_days', 'high')]
HEAVY_RAIN_DAYS_THRESHOLD = 3

d5 = bt.copy()
thr5 = {}
for feat, direction in DROUGHT_RULES_V5 + FLOOD_RULES:
    vals = d5[feat].dropna().values
    if feat == 'cumRain_mm':
        thr5[feat] = DISTRICT_LPA['Yavatmal'] * 1.20
    elif feat == 'heavy_rain_days':
        thr5[feat] = HEAVY_RAIN_DAYS_THRESHOLD
    elif direction == 'low':
        thr5[feat] = np.percentile(vals, 30)
    else:
        thr5[feat] = np.percentile(vals, 70)

for feat, direction in DROUGHT_RULES_V5 + FLOOD_RULES:
    if feat == 'cumRain_mm':
        d5[f'rule_{feat}'] = d5.apply(
            lambda row: row[feat] > DISTRICT_LPA.get(row['district'], 950) * 1.20, axis=1)
    elif direction == 'low':
        d5[f'rule_{feat}'] = d5[feat] < thr5[feat]
    else:
        d5[f'rule_{feat}'] = d5[feat] > thr5[feat]

drought_count5 = d5['rule_VHI_mean'].astype(int) + d5['rule_drySpellDays'].astype(int) + d5['rule_dry_spell_julaug'].astype(int)
d5['trigger_drought'] = drought_count5 >= 2
flood_count = d5['rule_cumRain_mm'].astype(int) + d5['rule_heavy_rain_days'].astype(int) + d5['rule_sm_wet_days'].astype(int)
d5['trigger_flood'] = flood_count >= 2
d5['trigger_any'] = d5['trigger_drought'] | d5['trigger_flood']
results['v5'] = metrics_for(d5, 'trigger_any')
print('v5 done:', results['v5'])

# ══════════════════════════ v6: 2-of-4 drought (+SMAP), 2-of-3 flood ═══════
d6 = bt.copy()
DROUGHT_RULES_V6 = DROUGHT_RULES_V5 + [('SMAP_sm_anom', 'low')]
thr6 = dict(thr5)
vals_smap = d6['SMAP_sm_anom'].dropna().values
thr6['SMAP_sm_anom'] = np.percentile(vals_smap, 30) if len(vals_smap) > 0 else 0

for feat, direction in DROUGHT_RULES_V6 + FLOOD_RULES:
    if feat == 'cumRain_mm':
        d6[f'rule_{feat}'] = d6.apply(
            lambda row: row[feat] > DISTRICT_LPA.get(row['district'], 950) * 1.20, axis=1)
    elif direction == 'low':
        d6[f'rule_{feat}'] = d6[feat] < thr6[feat]
    else:
        d6[f'rule_{feat}'] = d6[feat] > thr6[feat]
# SMAP is null pre-2015 -> rule is False (NaN comparison = False), matches original behavior
d6['rule_SMAP_sm_anom'] = d6['rule_SMAP_sm_anom'].fillna(False)

drought_count6 = (d6['rule_VHI_mean'].astype(int) + d6['rule_drySpellDays'].astype(int) +
                  d6['rule_dry_spell_julaug'].astype(int) + d6['rule_SMAP_sm_anom'].astype(int))
d6['trigger_drought'] = drought_count6 >= 2
flood_count6 = d6['rule_cumRain_mm'].astype(int) + d6['rule_heavy_rain_days'].astype(int) + d6['rule_sm_wet_days'].astype(int)
d6['trigger_flood'] = flood_count6 >= 2
d6['trigger_any'] = d6['trigger_drought'] | d6['trigger_flood']
results['v6'] = metrics_for(d6, 'trigger_any')
print('v6 done:', results['v6'])

# ══════════════════════════ v7/v8: CHF composite (entropy-weighted) ═══════
def run_chf(d, apy_z_col='crop_stress_z'):
    d = d.copy()
    CHF_COMPONENTS = {
        'NDVI_junjul': 'positive', 'NDVI_augsep': 'positive', 'NDVI_oct': 'positive',
        'FAPAR_mean': 'positive', 'SM_augsep': 'positive' if 'SM_augsep' in d.columns else None,
        'SAR_VH_augsep_dB': 'positive', 'rain_augsep_mm': 'positive', 'rain_junjul_mm': 'positive',
    }
    CHF_COMPONENTS = {k: v for k, v in CHF_COMPONENTS.items() if v is not None and k in d.columns}
    norm_params = {}
    for col, direction in CHF_COMPONENTS.items():
        vals = d[col].dropna()
        lo, hi = vals.quantile(0.02), vals.quantile(0.98)
        norm_params[col] = (lo, hi, direction)
    for col, (lo, hi, direction) in norm_params.items():
        normed = ((d[col] - lo) / (hi - lo)).clip(0, 1)
        if direction == 'negative':
            normed = 1 - normed
        d[f'{col}_norm'] = normed
    norm_cols = [f'{c}_norm' for c in CHF_COMPONENTS]

    D = d[norm_cols].dropna()
    n = len(D)
    k = 1.0 / np.log(n)
    weights = {}
    for col in norm_cols:
        p = D[col] / D[col].sum()
        p = p.replace(0, 1e-10)
        e = -k * (p * np.log(p)).sum()
        weights[col] = 1 - e
    total_w = sum(weights.values())
    weights = {c: w / total_w for c, w in weights.items()}

    chf = np.zeros(len(d))
    for col, w in weights.items():
        chf += d[col].fillna(0.5) * w
    d['CHF'] = chf

    # Calibrate strike against APY bad years (z < -0.5), F1-optimized
    dyc = d.groupby(['district', 'year'])['CHF'].mean().reset_index()
    dyc = dyc.merge(apy_raw[['district', 'year', apy_z_col]], on=['district', 'year'], how='inner')
    bad_mask = dyc[apy_z_col] < -0.5
    best_f1, best_thr = 0, 0.45
    for thr in np.arange(0.30, 0.65, 0.005):
        pred_bad = dyc['CHF'] < thr
        tp = (pred_bad & bad_mask).sum()
        fp = (pred_bad & ~bad_mask).sum()
        fn = (~pred_bad & bad_mask).sum()
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1v = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        if f1v > best_f1:
            best_f1, best_thr = f1v, thr

    d['trigger_drought'] = d['CHF'] < best_thr

    def flood_check(row):
        lpa = DISTRICT_LPA.get(row['district'], 950)
        augsep_lpa = lpa * 0.58
        return row['rain_augsep_mm'] > augsep_lpa * 1.20
    d['trigger_flood'] = d.apply(flood_check, axis=1)
    d['trigger_any'] = d['trigger_drought'] | d['trigger_flood']
    return d, best_thr

d7, strike7 = run_chf(bt.copy())
results['v7_v8_CHF'] = metrics_for(d7, 'trigger_any')
print(f'v7/v8 (CHF, strike={strike7:.3f}) done:', results['v7_v8_CHF'])

# ══════════════════════════ v9: Drought Index + Flood Index ════════════════
DI_FEATURES = {'LST_anom_C': -1, 'FAPAR_mean': 1, 'NDVI_augsep': 1, 'rain_junjul_mm': 1, 'drySpellDays': -1}
DI_WEIGHTS = {'LST_anom_C': 0.35, 'FAPAR_mean': 0.25, 'NDVI_augsep': 0.15, 'rain_junjul_mm': 0.15, 'drySpellDays': 0.10}
FI_FEATURES = {'rain_augsep_mm': 1, 'heavy_rain_days': 1, 'sm_wet_days': 1}
FI_WEIGHTS = {'rain_augsep_mm': 0.50, 'heavy_rain_days': 0.30, 'sm_wet_days': 0.20}

d9 = bt.copy()

def zscore_index(d, features, weights):
    idx = np.zeros(len(d))
    for feat, sign in features.items():
        z = np.zeros(len(d))
        for dist in d['district'].unique():
            vals = d.loc[d['district'] == dist, feat].dropna()
            mu, sigma = vals.mean(), vals.std()
            mask = d['district'] == dist
            raw = d.loc[mask, feat].fillna(mu)
            z[mask.values] = (raw - mu) / (sigma + 1e-9) * sign
        idx += z * weights[feat]
    return idx

d9['DI'] = zscore_index(d9, DI_FEATURES, DI_WEIGHTS)
d9['FI'] = zscore_index(d9, FI_FEATURES, FI_WEIGHTS)
DI_STRIKE = np.percentile(d9['DI'].dropna(), 28)
FI_STRIKE = np.percentile(d9['FI'].dropna(), 85)
d9['trigger_drought'] = d9['DI'] < DI_STRIKE
d9['trigger_flood'] = d9['FI'] > FI_STRIKE
d9['trigger_any'] = d9['trigger_drought'] | d9['trigger_flood']
results['v9'] = metrics_for(d9, 'trigger_any')
print('v9 done:', results['v9'])

# ══════════════════════════ Save & plot ════════════════════════════════════
res_df = pd.DataFrame(results).T
res_df.index.name = 'version'
res_df.to_csv('data/processed/version_comparison_metrics.csv')
print()
print(res_df.to_string())

# Bar chart comparison
fig, axes = plt.subplots(2, 2, figsize=(15, 11))
versions = list(results.keys())
colors = ['#d62728', '#ff7f0e', '#9467bd', '#2ca02c']

ax = axes[0, 0]
vals = [results[v]['f1'] for v in versions]
bars = ax.bar(versions, vals, color=colors, edgecolor='k')
ax.set_title('PMFBY F1 Score (2018–2024)', fontweight='bold')
ax.set_ylabel('F1')
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.01, f'{v:.2f}', ha='center')

ax = axes[0, 1]
prec = [results[v]['precision'] for v in versions]
rec = [results[v]['recall'] for v in versions]
x = np.arange(len(versions))
w = 0.35
ax.bar(x - w/2, prec, w, label='Precision', color='#1f77b4', edgecolor='k')
ax.bar(x + w/2, rec, w, label='Recall', color='#ff7f0e', edgecolor='k')
ax.set_xticks(x); ax.set_xticklabels(versions)
ax.set_title('PMFBY Precision vs Recall', fontweight='bold')
ax.legend()

ax = axes[1, 0]
vals = [results[v]['basis_risk'] for v in versions]
bars = ax.bar(versions, vals, color=colors, edgecolor='k')
ax.set_title('Basis Risk (PMFBY fires, we miss)', fontweight='bold')
ax.set_ylabel('Basis risk rate')
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.005, f'{v:.1%}', ha='center')

ax = axes[1, 1]
vals = [abs(results[v]['apy_trigger_corr']) if not np.isnan(results[v]['apy_trigger_corr']) else 0 for v in versions]
bars = ax.bar(versions, vals, color=colors, edgecolor='k')
ax.set_title('|Correlation| with APY Crop Stress (district-year)', fontweight='bold')
ax.set_ylabel('|Spearman ρ|')
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 0.01, f'{v:.2f}', ha='center')

plt.tight_layout()
plt.savefig(OUT / 'v9_version_comparison.png', dpi=150, bbox_inches='tight')
print('\nSaved -> vidarbha_outputs/v9_version_comparison.png')
