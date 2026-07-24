"""
merge_historical.py
────────────────────
Merges historical_features_2003_2017.csv with the existing 2018-2025 dataset
to produce a unified 23-year feature set for all 4 districts.

Output: data/processed/all_districts_23yr_features.csv
"""
import pandas as pd
import numpy as np
from pathlib import Path

HIST   = Path('data/processed/historical_features_2003_2017.csv')
CURR   = Path('data/processed/all_districts_final_features.csv')
CHF    = Path('data/processed/chf_features_all_districts.csv')
APY    = Path('data/processed/apy_district_yields.csv')
OUT    = Path('data/processed/all_districts_23yr_features.csv')

# ── Load current 2018-2025 (already has extra features merged in) ─────────────
curr = pd.read_csv(CURR)
print(f"Current 2018-2025: {curr.shape}  years={sorted(curr.year.unique())}")

# ── Load CHF sub-window features for 2018-2025 ────────────────────────────────
chf_curr = pd.read_csv(CHF)
chf_curr = chf_curr.rename(columns={'NDVI_anom_full': 'NDVI_anom_full_chf'})
merge_keys = ['district', 'taluka', 'revenue_circle', 'year']
curr = curr.merge(chf_curr[merge_keys + [c for c in chf_curr.columns if c not in merge_keys + list(curr.columns)]],
                  on=merge_keys, how='left')
print(f"After CHF merge: {curr.shape}")

# ── Load historical 2003-2017 ──────────────────────────────────────────────────
hist = pd.read_csv(HIST)
print(f"Historical 2003-2017: {hist.shape}  years={sorted(hist.year.unique())}")

# ── Align columns (union, fill missing with NaN) ──────────────────────────────
all_cols = sorted(set(curr.columns) | set(hist.columns))
curr_aligned = curr.reindex(columns=all_cols)
hist_aligned = hist.reindex(columns=all_cols)

combined = pd.concat([hist_aligned, curr_aligned], ignore_index=True)
combined = combined.sort_values(['district', 'taluka', 'revenue_circle', 'year']).reset_index(drop=True)

print(f"\nCombined dataset: {combined.shape}")
print(f"  Years: {sorted(combined.year.unique())}")
print(f"  Districts: {sorted(combined.district.unique())}")
print(f"  RCs: {combined.revenue_circle.nunique()}")

# ── Coverage summary ──────────────────────────────────────────────────────────
print("\nFeature coverage (non-null %):")
key_feats = ['NDVI_mean', 'LST_mean_C', 'VHI_mean', 'cumRain_mm',
             'FAPAR_mean', 'SM_mean', 'tmax_mean_C',
             'SMAP_sm_mean', 'SAR_VH_mean_dB',
             'NDVI_junjul', 'rain_junjul_mm', 'NDVI_augsep', 'rain_augsep_mm']
for f in key_feats:
    if f in combined.columns:
        pct = combined[f].notna().mean() * 100
        n = combined[f].notna().sum()
        print(f"  {f:25s}: {n:>5d}/{len(combined)} ({pct:.1f}%)")

# ── APY merge check ───────────────────────────────────────────────────────────
apy = pd.read_csv(APY)
# check overlap
sat_yrs = set(combined.year.unique())
apy_yrs = set(apy.year.unique())
overlap = sorted(sat_yrs & apy_yrs)
print(f"\nAPY overlap years: {overlap} (n={len(overlap)})")
print(f"District-year calibration points: {len(overlap) * 4}")

combined.to_csv(OUT, index=False)
print(f"\n✓ Saved → {OUT}")
print(f"  {len(combined)} rows  ×  {len(combined.columns)} columns")
