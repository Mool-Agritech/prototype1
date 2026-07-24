#!/usr/bin/env python3
"""
feature_weight_analysis_v2.py
─────────────────────────────
Updated version of Yug's feature_weight_analysis.py, incorporating:

  1. v3 dataset (8 years: 2018-2025, 880 rows, 764 with PMFBY)
  2. Heat features DROPPED (gdd_surplus CV=36%, lst_anom_augsep CV=832% in LOYO)
  3. Per-peril target alignment: drought weights from rate_yield, flood from rate_local
  4. Within-year correlation decomposition (§4 of Trigger_Threshold_Review_Notes.md)
  5. Leave-one-year-out (LOYO) weight stability check
  6. APY yield validation cross-check

Outputs:
  data/processed/feature_weight_analysis_v2.csv   — per-feature correlation table
  data/processed/feature_weight_analysis_v2.json  — full weight summary
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH   = ROOT / "data/processed/yavatmal_rc_model_ready_v3.csv"
OUTPUT_CSV  = ROOT / "data/processed/feature_weight_analysis_v2.csv"
OUTPUT_JSON = ROOT / "data/processed/feature_weight_analysis_v2.json"

# ── Config ────────────────────────────────────────────────────────────────────
BACKTEST_YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024]

# Per-peril feature groups and their stress direction
# Heat features excluded per Trigger_Threshold_Review_Notes.md §1
DROUGHT_FEATURES = {
    "VHI":            ("VHI_mean",         "low"),    # lower = more drought stress
    "DrySpellDays":   ("drySpellDays",     "high"),
    "DrySpellJulAug": ("dry_spell_julaug", "high"),
}
FLOOD_FEATURES = {
    "CumulativeRainfall":    ("cumRain_mm",      "high"),
    "HeavyRainDays":         ("heavy_rain_days", "high"),
    "SoilMoistureWetDays":   ("sm_wet_days",     "high"),
}

# Per-peril PMFBY target alignment:
#   drought weights should track yield-based loss (rate_yield)
#   flood weights should track localized loss (rate_local)
DROUGHT_TARGET = "rate_yield"
FLOOD_TARGET   = "rate_local"
COMPOSITE_TARGET = "rate_total"

# APY yield data for external validation
APY_COTTON = {
    2000: 91, 2001: 119, 2002: 132, 2003: 173, 2004: 146, 2005: 148,
    2006: 202, 2007: 412, 2008: 319, 2009: 220, 2010: 275, 2011: 252,
    2012: 357, 2013: 286, 2014: 319, 2015: 481, 2017: 173, 2018: 312,
    2019: 198, 2020: 274, 2021: 258, 2022: 207, 2023: 389, 2024: 290,
}


def minmax_norm(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mn, mx = s.min(), s.max()
    if pd.isna(mn) or pd.isna(mx) or np.isclose(mx, mn):
        return pd.Series(0.0, index=s.index)
    return (s - mn) / (mx - mn)


def corr_metrics(df: pd.DataFrame, feature: str, target: str) -> dict:
    valid = df[[feature, target]].dropna()
    if len(valid) < 5:
        return {"pearson": np.nan, "spearman": np.nan, "spearman_p": np.nan, "abs_mean": np.nan, "n": len(valid)}
    pearson  = float(valid[feature].corr(valid[target], method="pearson"))
    rho, pval = spearmanr(valid[feature], valid[target])
    abs_mean = float(np.nanmean([abs(pearson), abs(rho)]))
    return {"pearson": pearson, "spearman": float(rho), "spearman_p": float(pval), "abs_mean": abs_mean, "n": len(valid)}


def within_year_correlations(df: pd.DataFrame, feature: str, target: str, years: list) -> list[dict]:
    """Decompose pooled correlation into year-by-year (§4 of review notes)."""
    results = []
    for yr in years:
        sub = df[df["year"] == yr][[feature, target]].dropna()
        if len(sub) < 5:
            results.append({"year": yr, "n": len(sub), "spearman": np.nan, "p_value": np.nan})
            continue
        rho, pval = spearmanr(sub[feature], sub[target])
        results.append({"year": yr, "n": len(sub), "spearman": round(float(rho), 4), "p_value": round(float(pval), 4)})
    return results


def derive_group_weights(df: pd.DataFrame, feature_group: dict, target: str) -> tuple[pd.DataFrame, dict]:
    """Derive within-group weights from avg abs(pearson, spearman) correlation with target."""
    rows = []
    for name, (col, direction) in feature_group.items():
        # For "low" features (VHI), negate so higher correlation = more stress
        if direction == "low":
            feat_vals = -df[col]
        else:
            feat_vals = df[col]
        tmp = df.copy()
        tmp["_feat"] = feat_vals
        metrics = corr_metrics(tmp, "_feat", target)
        metrics["feature_name"] = name
        metrics["source_column"] = col
        metrics["direction"] = direction
        rows.append(metrics)

    weight_df = pd.DataFrame(rows)
    weight_df["weight"] = weight_df["abs_mean"].abs()
    total = weight_df["weight"].sum()
    if not np.isfinite(total) or total <= 0:
        weight_df["weight"] = 0.0
    else:
        weight_df["weight"] = weight_df["weight"] / total

    return weight_df, {r["feature_name"]: r["weight"] for _, r in weight_df.iterrows()}


def loyo_weight_stability(df: pd.DataFrame, feature_group: dict, target: str, years: list) -> dict:
    """Leave-one-year-out: re-derive weights excluding each year, report CV."""
    all_weights = {name: [] for name in feature_group}
    for drop_yr in years:
        sub = df[df["year"] != drop_yr]
        _, weights = derive_group_weights(sub, feature_group, target)
        for name, w in weights.items():
            all_weights[name].append(w)

    stability = {}
    for name, w_list in all_weights.items():
        arr = np.array(w_list)
        stability[name] = {
            "mean": round(float(arr.mean()), 4),
            "std": round(float(arr.std()), 4),
            "cv_pct": round(float(arr.std() / arr.mean() * 100), 1) if arr.mean() > 0 else np.nan,
            "range": [round(float(arr.min()), 4), round(float(arr.max()), 4)],
        }
    return stability


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    bt = df[df["year"].isin(BACKTEST_YEARS)].copy()
    print(f"Dataset: {len(df)} total rows, {len(bt)} backtest rows (years {BACKTEST_YEARS})")
    print(f"  Rows with rate_total: {bt['rate_total'].notna().sum()}")
    print(f"  Rows with rate_yield: {bt[DROUGHT_TARGET].notna().sum()}")
    print(f"  Rows with rate_local: {bt[FLOOD_TARGET].notna().sum()}")

    # ── 1. Pooled correlations for all features ──────────────────────────────
    all_features = list({col for _, (col, _) in {**DROUGHT_FEATURES, **FLOOD_FEATURES}.items()})
    feature_rows = []
    for feat in all_features:
        if feat not in bt.columns:
            continue
        pooled = corr_metrics(bt, feat, COMPOSITE_TARGET)
        within = within_year_correlations(bt, feat, COMPOSITE_TARGET, BACKTEST_YEARS)
        # Count years with significant (p<0.05) positive correlation
        sig_positive = sum(1 for w in within if w["spearman"] is not np.nan
                          and not np.isnan(w.get("spearman", np.nan))
                          and w["p_value"] < 0.05 and w["spearman"] > 0)
        sig_negative = sum(1 for w in within if w["spearman"] is not np.nan
                          and not np.isnan(w.get("spearman", np.nan))
                          and w["p_value"] < 0.05 and w["spearman"] < 0)
        feature_rows.append({
            "feature": feat,
            "pooled_pearson": round(pooled["pearson"], 4),
            "pooled_spearman": round(pooled["spearman"], 4),
            "pooled_p": round(pooled["spearman_p"], 6),
            "abs_mean": round(pooled["abs_mean"], 4),
            "n": pooled["n"],
            "years_sig_positive": sig_positive,
            "years_sig_negative": sig_negative,
            "within_year_detail": within,
        })

    feature_summary = pd.DataFrame(feature_rows).sort_values("abs_mean", ascending=False)
    print("\n=== POOLED CORRELATIONS (all features vs rate_total) ===")
    print(feature_summary[["feature", "pooled_spearman", "pooled_p", "years_sig_positive", "years_sig_negative"]].to_string(index=False))

    # ── 2. Per-peril weights (key improvement: different targets) ────────────
    print(f"\n=== DROUGHT WEIGHTS (target: {DROUGHT_TARGET}) ===")
    drought_df, drought_w = derive_group_weights(bt, DROUGHT_FEATURES, DROUGHT_TARGET)
    print(drought_df[["feature_name", "pearson", "spearman", "weight"]].to_string(index=False))

    print(f"\n=== FLOOD WEIGHTS (target: {FLOOD_TARGET}) ===")
    flood_df, flood_w = derive_group_weights(bt, FLOOD_FEATURES, FLOOD_TARGET)
    print(flood_df[["feature_name", "pearson", "spearman", "weight"]].to_string(index=False))

    # ── 3. LOYO weight stability ─────────────────────────────────────────────
    print("\n=== LOYO WEIGHT STABILITY ===")
    drought_stability = loyo_weight_stability(bt, DROUGHT_FEATURES, DROUGHT_TARGET, BACKTEST_YEARS)
    flood_stability   = loyo_weight_stability(bt, FLOOD_FEATURES, FLOOD_TARGET, BACKTEST_YEARS)

    print("Drought:")
    for name, s in drought_stability.items():
        print(f"  {name:18s}  weight={s['mean']:.3f}  CV={s['cv_pct']:.1f}%  range=[{s['range'][0]:.3f}, {s['range'][1]:.3f}]")
    print("Flood:")
    for name, s in flood_stability.items():
        print(f"  {name:18s}  weight={s['mean']:.3f}  CV={s['cv_pct']:.1f}%  range=[{s['range'][0]:.3f}, {s['range'][1]:.3f}]")

    # ── 4. Compute per-peril stress scores ───────────────────────────────────
    # Normalize features (0-1, stress-oriented: higher = more stress)
    for name, (col, direction) in DROUGHT_FEATURES.items():
        normed = minmax_norm(bt[col])
        bt[f"{name}_norm"] = (1.0 - normed) if direction == "low" else normed

    for name, (col, direction) in FLOOD_FEATURES.items():
        bt[f"{name}_norm"] = minmax_norm(bt[col])

    bt["Drought_Score"] = sum(drought_w[n] * bt[f"{n}_norm"] for n in drought_w)
    bt["Flood_Score"]   = sum(flood_w[n]   * bt[f"{n}_norm"] for n in flood_w)

    # Composite: derive weight from each sub-score's correlation with rate_total
    comp_rows = []
    for comp in ["Drought_Score", "Flood_Score"]:
        m = corr_metrics(bt, comp, COMPOSITE_TARGET)
        comp_rows.append({"component": comp, **m})
    comp_df = pd.DataFrame(comp_rows)
    comp_df["weight"] = comp_df["abs_mean"].abs()
    total_cw = comp_df["weight"].sum()
    comp_df["weight"] = comp_df["weight"] / total_cw if total_cw > 0 else 0
    comp_w = {r["component"]: r["weight"] for _, r in comp_df.iterrows()}

    bt["Composite_Stress_Score"] = (
        comp_w["Drought_Score"] * bt["Drought_Score"]
        + comp_w["Flood_Score"] * bt["Flood_Score"]
    )

    print(f"\n=== COMPOSITE WEIGHTS ===")
    print(comp_df[["component", "weight", "pearson", "spearman"]].to_string(index=False))

    # ── 5. Validate against APY cotton yield ─────────────────────────────────
    print("\n=== APY COTTON YIELD VALIDATION ===")
    yr_means = bt.groupby("year").agg(
        drought_score=("Drought_Score", "mean"),
        flood_score=("Flood_Score", "mean"),
        composite=("Composite_Stress_Score", "mean"),
        rate_total=("rate_total", "mean"),
    ).reset_index()
    yr_means["cotton_yield"] = yr_means["year"].map(APY_COTTON)

    valid_apy = yr_means.dropna(subset=["cotton_yield"])
    if len(valid_apy) >= 4:
        # Higher stress score should correlate with LOWER yield
        for col in ["drought_score", "flood_score", "composite"]:
            rho, pval = spearmanr(valid_apy[col], valid_apy["cotton_yield"])
            direction = "✓ correct" if rho < 0 else "✗ WRONG direction"
            print(f"  {col:20s} vs cotton_yield: rho={rho:+.3f} (p={pval:.3f}) {direction}")
    else:
        print("  Insufficient APY overlap for validation.")

    print("\n  Year-by-year:")
    for _, r in yr_means.iterrows():
        yr = int(r["year"])
        cy = APY_COTTON.get(yr, None)
        cy_str = f"{cy:4d} kg/ha" if cy else "  N/A     "
        print(f"    {yr}  drought={r['drought_score']:.3f}  flood={r['flood_score']:.3f}  "
              f"composite={r['composite']:.3f}  PMFBY_rate={r['rate_total']:.3f}  cotton={cy_str}")

    # ── 6. Within-year correlation deep dive (§4 validation) ─────────────────
    print("\n=== WITHIN-YEAR CORRELATION DECOMPOSITION (§4 check) ===")
    key_pairs = [
        ("drySpellDays", DROUGHT_TARGET, "drought"),
        ("cumRain_mm",   FLOOD_TARGET,   "flood"),
        ("VHI_mean",     DROUGHT_TARGET, "drought"),
    ]
    for feat, target, peril in key_pairs:
        print(f"\n  {feat} vs {target}:")
        within = within_year_correlations(bt, feat, target, BACKTEST_YEARS)
        pooled = corr_metrics(bt, feat, target)
        print(f"    Pooled: rho={pooled['spearman']:+.3f} (p={pooled['spearman_p']:.4f}, n={pooled['n']})")
        for w in within:
            sig = "***" if w["p_value"] < 0.01 else ("**" if w["p_value"] < 0.05 else ("*" if w["p_value"] < 0.1 else ""))
            rho_str = f"{w['spearman']:+.3f}" if not np.isnan(w.get("spearman", np.nan)) else "   N/A"
            print(f"    {w['year']}: rho={rho_str}  p={w['p_value']:.3f}  n={w['n']:3d} {sig}")

    # ── 7. Save outputs ──────────────────────────────────────────────────────
    save_df = feature_summary.drop(columns=["within_year_detail"], errors="ignore")
    save_df.to_csv(OUTPUT_CSV, index=False)

    payload = {
        "data_version": "v3 (2018-2025, 880 rows)",
        "backtest_years": BACKTEST_YEARS,
        "heat_features": "EXCLUDED — see Trigger_Threshold_Review_Notes.md §1",
        "methodology": {
            "drought_target": DROUGHT_TARGET,
            "flood_target": FLOOD_TARGET,
            "composite_target": COMPOSITE_TARGET,
            "weighting_method": "avg abs(Pearson, Spearman) with peril-specific target, then normalized",
            "key_improvement_over_v1": "per-peril target alignment + LOYO stability + within-year decomposition",
        },
        "drought_weights": drought_w,
        "flood_weights": flood_w,
        "composite_weights": comp_w,
        "loyo_stability": {
            "drought": drought_stability,
            "flood": flood_stability,
        },
        "feature_correlations": feature_summary.drop(columns=["within_year_detail"], errors="ignore").to_dict(orient="records"),
        "composite_correlations": comp_df.to_dict(orient="records"),
        "apy_validation": yr_means.to_dict(orient="records"),
    }
    with OUTPUT_JSON.open("w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\n✓ Saved {OUTPUT_CSV}")
    print(f"✓ Saved {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
