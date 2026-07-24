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

## 4. Pooling all 4 years together hides/distorts the real signal

Same root cause as §1, showing up in a second place. The percentile thresholds (`cell-5` in `Vidarbha_ModelExperiment.ipynb`) are computed by dumping all 4 years' RC×year rows into one flat array and taking `np.percentile()` — no awareness of which row belongs to which year. When we tried to validate whether `drySpellDays` actually tracks real loss (`rate_yield`, PMFBY's drought-specific payout), the same pooling shows up again and produces a misleading number.

**Pooled correlation** (all 388 rows, years mixed): `drySpellDays` vs `rate_yield` → spearman = **−0.30** (p<0.0001, looks solid). Naive read: "more dry days → *less* PMFBY payout," which is backwards from what we'd expect.

**Decomposed by year, the picture is much messier:**

| Comparison | Result |
| ----------- | ------ |
| Between-year (4 yearly means only) | spearman = −0.40 — driven almost entirely by 2023: highest dry-day average (101 days), lowest payout average (0.3%) |
| Within-year 2021 (RCs vs each other) | **+0.34** (p<0.001) — the expected direction |
| Within-year 2022 | **−0.30** (p=0.007) — significant, but *wrong* direction |
| Within-year 2023 | −0.15 (not significant) |
| Within-year 2024 | −0.06 (not significant) |

Only **1 of 4 years** (2021) actually shows "more dry days → more loss" internally. The headline pooled number (−0.30) isn't a clean signal being masked by confounding — it's mostly just **2023's extreme position (high dry-days, ~zero payout) dominating a 388-row average**, the same way one outlier year can swing a 4-point percentile threshold in the LOYO check in §1.

**Why this happens:** "year" acts as a lurking variable — it's correlated with both `drySpellDays` (some years are objectively drier) and `rate_yield` (PMFBY's own payout behavior swings a lot year to year, for reasons unrelated to any single RC's dry-spell count — e.g. whether that year's CCE captured the loss at all). Mixing years together in one correlation or one percentile computation blends the "does this feature track loss *within* a season" question with "how different were the years from each other," and the second one dominates when sample size per year is small and one year (2023) is an outlier.

---

## 5. We currently only have "does it trigger," not "how much it pays" — WBCIS has the official formula

Checked our notebook: `trigger_any` and friends are pure booleans. There's no payout-amount calculation anywhere — cell at the end of `Vidarbha_ModelExperiment.ipynb` literally lists "price the product: expected payout rate × sum insured → premium loading" as a *future* step. The Finance team's ₹3,000–6,000/acre (10–25% of sum insured) number is a placeholder assumption, not derived from our model.

**Source:** *Restructured Weather Based Crop Insurance Scheme (WBCIS) — Operational Guidelines*, DAC&FW, March 2016 (§XV.8, §XIX). This is the actual Indian government template for exactly this kind of weather-index payout — worth using directly instead of inventing our own structure.

**The official formula (§XV.8):**

```
Claims per Unit = (Observed index − Notified index) × Notional Payout
Overall claims   = Claims per Unit × Number of units (hectares)
```

Structured as a **tiered payout**, not a single binary trigger:

| Parameter | Meaning |
| --- | --- |
| Strike 1 | Where payout starts (≈ our current "trigger threshold") |
| Strike 2 | Second breakpoint, payout rate changes |
| Exit | Beyond this, full Policy Limit is paid (capped) |
| Notional 1 | Rs/mm(or unit)/hectare rate between Strike 1 and Strike 2 |
| Notional 2 | Rate between Strike 2 and Exit (steeper — more severe = paid more) |
| Policy Limit | Max payout per hectare for that phase |

Worked example from the guideline: Strike1=200mm, Strike2=150mm, Exit=100mm, Notional1=50, Notional2=80, Policy Limit=₹6,500/ha. Observed=120mm → claim = (200−150)×50 + (150−120)×80 = **₹4,900/ha**. Observed=80mm (below Exit) → full ₹6,500/ha capped payout.

**There's also a stepped/discrete version (§XIX, "Index C") that maps directly onto our `drySpellDays`-style features** — Consecutive Dry Days (CDD), dry day defined as ≤2.5mm rainfall (matches the IMD definition we already use, good cross-check):

| CDD range | Payout (Rs/hectare) |
| --- | --- |
| Strike1 (4) → Strike2 (10) | 328 |
| Strike2 (10) → Strike3 (14) | 720 |
| Strike3 (14) → Strike4 (19) | 1,800 |
| Strike4 (19) → Exit (24) | 3,600 |
| beyond Exit (24) | 6,000 (capped) |

**How this maps onto our 8 features:**
- `drySpellDays` / `dry_spell_julaug` → stepped CDD structure above, direct fit
- `cumRain_mm` → continuous linear Strike/Notional/Exit structure (Index A/B in the guideline)
- `heavy_rain_days` → "Excess Rainfall on a Single Day" trigger (single-day threshold + payout rate)

**One line from the guideline worth flagging to the team directly** (§IV.3): *"Too conservative triggers tend to lead to frequent but smaller payouts, diluting the indemnity principle of insurance."* This is the official regulator naming the exact failure mode we found in §1 — `trigger_any` firing 75% of the time in backtest is a symptom of exactly this.

**Action:** replace the current binary `trigger_any` with a Strike1/Strike2/Exit tiered structure per peril, using this template. Gives us both a defensible payout amount (was missing) and a natural place to fix the "OR logic inflates sensitivity" problem from §1 (tiering means low-severity RCs get small payouts instead of the same full trigger as extreme ones).

---

## 6. Suggested next steps

1. **Quick win:** swap `cumRain_mm` and `heavy_rain_days` thresholds for the IMD standards above — these are ready to go, just need the district LPA baseline number sourced.
2. **Decide on VHI** — Option A (relabel as internal percentile, no claim to international standard) vs Option B (rebuild dekadal, real effort, but defensible against Kogan/FAO). Recommend Option A for the pitch deadline, Option B as a post-pitch improvement.
3. **Heat features are the weakest link statistically** (`gdd_surplus`, `lst_anom_augsep` — CV 36–832% in LOYO). Only 4 years of data and no external standard yet for the percentile layer. Treat heat trigger results with the most caution until we either get more years of baseline or find an agronomic anchor.
4. **Build the actual payout formula** using the WBCIS Strike/Notional/Exit template in §5 — this is the biggest functional gap: we can currently say "should this pay out" but not "how much."
