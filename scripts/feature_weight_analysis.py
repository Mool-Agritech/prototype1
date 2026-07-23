#!/usr/bin/env python3
"""Compute feature correlations and derive stress-score weights for Vidarbha crop stress modeling.

The script reads the processed model-ready CSV, evaluates each candidate feature against
an outcome variable (default: rate_yield), normalizes the features into 0-1 stress inputs,
and derives component weights for:

- Drought Score = w1*(1 - VHI_norm) + w2*DrySpellDays_norm + w3*DrySpellJulAug_norm
- Flood Score = w1*CumulativeRainfall_norm + w2*HeavyRainDays_norm + w3*SoilMoistureWetDays_norm
- Heat Score = w1*LST_Anomaly_norm + w2*GDD_Surplus_norm
- Composite Crop Stress Score = w1*Drought Score + w2*Flood Score + w3*Heat Score

The script also saves correlation tables and a JSON summary for downstream use.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data/processed/yavatmal_rc_model_ready_v2.csv"
OUTPUT_CSV = ROOT / "data/processed/feature_weight_analysis.csv"
OUTPUT_JSON = ROOT / "data/processed/feature_weight_analysis.json"


def minmax_norm(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mn = s.min()
    mx = s.max()
    if pd.isna(mn) or pd.isna(mx) or np.isclose(mx, mn):
        return pd.Series(0.0, index=s.index)
    return (s - mn) / (mx - mn)


def corr_metrics(df: pd.DataFrame, feature: str, target: str) -> Dict[str, float]:
    valid = df[[feature, target]].dropna()
    if len(valid) < 3:
        return {"pearson": np.nan, "spearman": np.nan, "abs_mean": np.nan}

    pearson = valid[feature].corr(valid[target], method="pearson")
    spearman = valid[feature].corr(valid[target], method="spearman")
    abs_mean = float(np.nanmean([abs(pearson), abs(spearman)]))
    return {
        "pearson": float(pearson),
        "spearman": float(spearman),
        "abs_mean": abs_mean,
    }


def derive_group_weights(df: pd.DataFrame, feature_group: Dict[str, str], target: str) -> Tuple[pd.DataFrame, Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    for feature_name, feature_col in feature_group.items():
        metrics = corr_metrics(df, feature_col, target)
        rows.append(
            {
                "feature_name": feature_name,
                "source_column": feature_col,
                "pearson": metrics["pearson"],
                "spearman": metrics["spearman"],
                "abs_mean": metrics["abs_mean"],
            }
        )

    weight_df = pd.DataFrame(rows)
    if weight_df.empty:
        return weight_df, {}

    weight_df["weight"] = weight_df["abs_mean"].abs()
    total_weight = weight_df["weight"].sum()
    if not np.isfinite(total_weight) or total_weight <= 0:
        weight_df["weight"] = 0.0
    else:
        weight_df["weight"] = weight_df["weight"] / total_weight

    weight_map = {row["feature_name"]: row["weight"] for _, row in weight_df.iterrows()}
    return weight_df, weight_map


def rescale_0_100(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    mn = s.min()
    mx = s.max()
    if pd.isna(mn) or pd.isna(mx) or np.isclose(mx, mn):
        return pd.Series(0.0, index=s.index)
    return (s - mn) / (mx - mn) * 100.0


def main() -> None:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Expected data file not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)

    target_candidates = [
        col for col in ["rate_yield", "rate_total", "rate_local", "rate_prevented", "rate_postharvest", "rate_midterm", "claim_ratio"]
        if col in df.columns
    ]
    if not target_candidates:
        raise ValueError("No suitable target column found in the processed dataset.")
    target = target_candidates[0]

    print(f"Using target column: {target}")

    # 1) Correlations for individual features across the dataset.
    feature_candidates = [
        "VHI_mean",
        "drySpellDays",
        "dry_spell_julaug",
        "cumRain_mm",
        "heavy_rain_days",
        "sm_wet_days",
        "lst_anom_augsep",
        "gdd_surplus",
    ]
    feature_rows: List[Dict[str, object]] = []
    for feature in feature_candidates:
        if feature in df.columns:
            metrics = corr_metrics(df, feature, target)
            feature_rows.append(
                {
                    "feature": feature,
                    "missing_pct": df[feature].isna().mean() * 100.0,
                    "mean": df[feature].mean(),
                    "std": df[feature].std(),
                    "pearson": metrics["pearson"],
                    "spearman": metrics["spearman"],
                    "abs_mean": metrics["abs_mean"],
                }
            )

    feature_summary = pd.DataFrame(feature_rows).sort_values("abs_mean", ascending=False)

    # 2) Build normalized feature columns for each stress family.
    drought_features = {
        "VHI": "VHI_mean",
        "DrySpellDays": "drySpellDays",
        "DrySpellJulAug": "dry_spell_julaug",
    }
    flood_features = {
        "CumulativeRainfall": "cumRain_mm",
        "HeavyRainDays": "heavy_rain_days",
        "SoilMoistureWetDays": "sm_wet_days",
    }
    heat_features = {
        "LST_Anomaly": "lst_anom_augsep",
        "GDD_Surplus": "gdd_surplus",
    }

    # Higher raw values indicate more stress for most features; VHI is inverted.
    df["VHI_norm"] = minmax_norm(df["VHI_mean"])
    df["DrySpellDays_norm"] = minmax_norm(df["drySpellDays"])
    df["DrySpellJulAug_norm"] = minmax_norm(df["dry_spell_julaug"])
    df["CumulativeRainfall_norm"] = minmax_norm(df["cumRain_mm"])
    df["HeavyRainDays_norm"] = minmax_norm(df["heavy_rain_days"])
    df["SoilMoistureWetDays_norm"] = minmax_norm(df["sm_wet_days"])
    df["LST_Anomaly_norm"] = minmax_norm(df["lst_anom_augsep"])
    df["GDD_Surplus_norm"] = minmax_norm(df["gdd_surplus"])

    # Create stress-oriented versions where higher = more stress.
    df["VHI_stress_norm"] = 1.0 - df["VHI_norm"]

    # 3) Derive within-component weights.
    drought_weight_df, drought_weights = derive_group_weights(df, drought_features, target)
    flood_weight_df, flood_weights = derive_group_weights(df, flood_features, target)
    heat_weight_df, heat_weights = derive_group_weights(df, heat_features, target)

    # 4) Compute sub-scores using the derived weights.
    drought_score = (
        drought_weights["VHI"] * df["VHI_stress_norm"]
        + drought_weights["DrySpellDays"] * df["DrySpellDays_norm"]
        + drought_weights["DrySpellJulAug"] * df["DrySpellJulAug_norm"]
    )
    flood_score = (
        flood_weights["CumulativeRainfall"] * df["CumulativeRainfall_norm"]
        + flood_weights["HeavyRainDays"] * df["HeavyRainDays_norm"]
        + flood_weights["SoilMoistureWetDays"] * df["SoilMoistureWetDays_norm"]
    )
    heat_score = (
        heat_weights["LST_Anomaly"] * df["LST_Anomaly_norm"]
        + heat_weights["GDD_Surplus"] * df["GDD_Surplus_norm"]
    )

    df["Drought_Score"] = drought_score
    df["Flood_Score"] = flood_score
    df["Heat_Score"] = heat_score

    # 5) Derive higher-level composite weights from the sub-scores.
    subscore_df = pd.DataFrame(
        {
            "component": ["Drought_Score", "Flood_Score", "Heat_Score"],
            "score": [df["Drought_Score"], df["Flood_Score"], df["Heat_Score"]],
        }
    )
    component_corr_rows = []
    for component in ["Drought_Score", "Flood_Score", "Heat_Score"]:
        metrics = corr_metrics(df, component, target)
        component_corr_rows.append(
            {
                "component": component,
                "pearson": metrics["pearson"],
                "spearman": metrics["spearman"],
                "abs_mean": metrics["abs_mean"],
            }
        )
    component_corr_df = pd.DataFrame(component_corr_rows)
    component_corr_df["weight"] = component_corr_df["abs_mean"].abs()
    total_component_weight = component_corr_df["weight"].sum()
    if not np.isfinite(total_component_weight) or total_component_weight <= 0:
        component_corr_df["weight"] = 0.0
    else:
        component_corr_df["weight"] = component_corr_df["weight"] / total_component_weight

    component_weights = {
        row["component"]: row["weight"] for _, row in component_corr_df.iterrows()
    }

    df["Composite_Crop_Stress_Score"] = (
        component_weights["Drought_Score"] * df["Drought_Score"]
        + component_weights["Flood_Score"] * df["Flood_Score"]
        + component_weights["Heat_Score"] * df["Heat_Score"]
    )

    # 6) Rescale all component and composite scores to 0-100.
    for score_col in ["Drought_Score", "Flood_Score", "Heat_Score", "Composite_Crop_Stress_Score"]:
        df[f"{score_col}_0_100"] = rescale_0_100(df[score_col])

    # 7) Save outputs.
    feature_summary.to_csv(OUTPUT_CSV, index=False)

    summary_payload = {
        "target": target,
        "weighting_method": "average absolute Pearson and Spearman correlation with target, then normalized",
        "drought_weights": drought_weights,
        "flood_weights": flood_weights,
        "heat_weights": heat_weights,
        "composite_weights": component_weights,
        "feature_summary": feature_summary.to_dict(orient="records"),
        "component_correlations": component_corr_df.to_dict(orient="records"),
    }
    with OUTPUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary_payload, fh, indent=2, default=str)

    print("\nFeature correlation summary")
    print(feature_summary[["feature", "pearson", "spearman", "abs_mean"]].to_string(index=False))

    print("\nSuggested component weights")
    print(pd.DataFrame(
        [
            {"component": "Drought", **{k: v for k, v in drought_weights.items()}},
            {"component": "Flood", **{k: v for k, v in flood_weights.items()}},
            {"component": "Heat", **{k: v for k, v in heat_weights.items()}},
        ]
    ).to_string(index=False))

    print("\nComposite weights")
    print(component_corr_df[["component", "weight", "pearson", "spearman"]].to_string(index=False))

    print(f"\nSaved feature summary to {OUTPUT_CSV}")
    print(f"Saved JSON summary to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
