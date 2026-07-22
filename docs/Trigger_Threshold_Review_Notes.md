# Trigger Threshold Review — Notes for the Team

> Context: `Vidarbha_ModelExperiment.ipynb` sets all 8 trigger features (drought/flood/heat) using percentile cutoffs (p30 for "low" features, p70 for "high" features) computed on just our 4 backtest years (2021–2024). Flagged as too arbitrary — this doc captures what we checked and what we found.

---

## 1. The core problem: percentile thresholds are noisy with only 4 years

Ran a leave-one-year-out (LOYO) stability check: recompute each threshold excluding one year at a time, see how much it moves.

| Feature             | Full (4yr) threshold | Range across LOYO | CV%   | Stability   |
| -------------------- | --------------------: | -----------------: | -----: | ----------- |
| VHI_mean             | 0.597                | 3.7%               | 1.6%   | ✅ stable    |
| sm_wet_days          | 111.07                | 3.9%               | 1.6%   | ✅ stable    |
| cumRain_mm           | 1292.3                | 16.0%              | 6.6%   | ⚠️ moderate |
| dry_spell_julaug     | 26.34                 | 18.3%              | 7.6%   | ⚠️ moderate |
| drySpellDays         | 83.96                 | 22.1%              | 8.5%   | ⚠️ moderate |
| gdd_surplus          | 0.114                 | 138%               | 36.6%  | 🔴 unstable |
| heavy_rain_days      | 3.05                  | 93.9%              | 34.2%  | 🔴 unstable |
| lst_anom_augsep      | 0.065                 | 1006%              | 832.1% | 🔴 unstable |

Worse: across **all 8 features**, 11–18% of individual RC×year trigger decisions flip depending on which single year is excluded from threshold calibration. That's a real fairness problem, not just an academic one — whether a farmer's satellite trigger fires can hinge on which years happened to be in the baseline sample.

Also worth remembering: 3 rules OR'd per peril, 3 perils OR'd together → even if each rule is set to a "sensible" p70 (~30% marginal fire rate), the combined `trigger_any` fires 75% of the time in backtest. The OR logic inflates sensitivity well beyond what any single percentile choice implies — we haven't corrected for this anywhere.

**Takeaway:** heat features (`gdd_surplus`, `lst_anom_augsep`) are currently too unstable to trust. `heavy_rain_days` too. VHI and `sm_wet_days` are fine as-is, statistically.

---

## 2. VHI — the more interesting problem (two options)

Checked `VHI_mean` against the internationally standard Kogan classification (0–100 scale: <10 extreme drought, 10–20 severe, 20–30 moderate, 30–40 mild, >40 no drought).

**Our formula is correct** (`Yavatmal_RC_DataCollection.ipynb`, VHI block): `VHI = 0.5·VCI + 0.5·TCI`, textbook Kogan, with VCI/TCI baselined off 10 years (2016–2026) of MODIS NDVI/LST min-max. The baseline length isn't the issue.

**The scale doesn't line up.** `VHI_mean` in our data ranges 0.516–0.799 (i.e. 51.6–79.9 on the 0–100 scale) — entirely above Kogan's "no drought" line (>40), even in 2023, our worst drought year. Root cause: our code computes `ndvi_now = ndvi_col.mean()` / `lst_now = lst_col.mean()` — the **mean NDVI/LST over the whole Jun–Oct season** — and compares that to the 10-year min/max. Kogan's method is meant to run at **dekadal (10-day) resolution**, catching a single sharp stress window. Averaging over 5 months structurally pulls the value toward the middle of the range, away from the extremes that define the baseline — so our seasonal-mean VHI can basically never approach true Kogan drought territory, independent of how bad the season actually was.

**Two ways to fix, pick one:**

- **Option A — keep season-mean VHI, drop the idea of borrowing Kogan's absolute cutoffs.** Our VHI isn't on the same footing as literature VHI once it's been season-averaged, so 10/20/30/40 don't transfer. Stick with a percentile approach for this feature specifically (it's already the most stable one per the LOYO check above), just don't claim it's "the internationally recognized drought threshold."
- **Option B — rebuild VHI at native dekadal resolution.** Change the GEE aggregation in `Yavatmal_RC_DataCollection.ipynb` to output per-dekad VHI instead of one season-mean number, then define the trigger as something like "N dekads with VHI < 35 during the season." This is how FAO ASIS / NOAA actually use VHI operationally, and it would let us cite Kogan's thresholds legitimately. Real effort: re-pull the GEE time series, rewrite the feature engineering and the trigger logic to work over a season of dekadal values instead of one scalar per RC×year.

Not resolved yet — needs a call on whether Option B's rework is worth it before the pitch deadline, or whether Option A (be honest that it's an internal percentile, not a global standard) is good enough for now.

---

## 3. Other features — official standards found (ready to use)

| Feature                | Current approach          | Official standard found                                                                                                                    | Action |
| ----------------------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| `cumRain_mm` (seasonal total) | p70 of 4-yr sample   | **IMD monsoon rainfall classification** (% of Long Period Average, LPA): Excess >120% LPA, Normal 81–119%, Deficient 41–80%, Scanty ≤40% | Swap p70 for ">120% of Yavatmal/Vidarbha LPA" — need to source the district LPA figure. |
| `heavy_rain_days`        | p70 of 4-yr sample (underlying day cutoff ~50mm) | **IMD daily rainfall intensity classes**: heavy rain 64.5–115.5mm/day, very heavy 115.6–204.4mm/day, extremely heavy >204.4mm/day | Swap the ~50mm/day cutoff for IMD's 64.5mm ("heavy") or 115.6mm ("very heavy") depending on desired severity. |
| `gdd_surplus` (heat, base 35°C) | p70 of anomaly        | **Cotton photosynthesis stress threshold >35°C is already what we use** — matches ag literature (Univ. of Arizona cotton heat stress bulletin; Bayer Crop Science). Base temp itself is fine. | Keep the 35°C base. Only the p70-on-the-anomaly layer is still arbitrary — no external number found yet for "how many days above 35°C causes yield loss" at this crop stage; needs a more targeted agronomy search if we want to fix this too. |
| `drySpellDays` / `dry_spell_julaug` | p70 of 4-yr sample | IMD defines a "dry day" as <2.5mm rainfall — useful for how the day-count itself is built, but no official standard found yet for "how many consecutive/total dry days = drought" at crop-stage level. | Needs more targeted search (crop-stage critical dry-spell-length literature for cotton/soybean/tur in this region) if we want an external anchor here too. |
| `VHI_mean`               | p30 of 4-yr sample         | See §2 — Kogan 0–100 scale doesn't transfer directly given season-mean aggregation.                                                        | See §2. |
| `sm_wet_days`            | p70 of 4-yr sample         | No official waterlogging-day standard found yet.                                                                                            | Lower priority — this feature is already stable per the LOYO check. |

---

## 4. Suggested next steps

1. **Quick win:** swap `cumRain_mm` and `heavy_rain_days` thresholds for the IMD standards above — these are ready to go, just need the district LPA baseline number sourced.
2. **Decide on VHI** — Option A (relabel as internal percentile, no claim to international standard) vs Option B (rebuild dekadal, real effort, but defensible against Kogan/FAO). Recommend Option A for the pitch deadline, Option B as a post-pitch improvement.
3. **Heat features are the weakest link statistically** (`gdd_surplus`, `lst_anom_augsep` — CV 36–832% in LOYO). Only 4 years of data and no external standard yet for the percentile layer. Treat heat trigger results with the most caution until we either get more years of baseline or find an agronomic anchor.
