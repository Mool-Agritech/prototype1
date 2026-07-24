# Workstream B – Revision

**1. CLIMATE RISK TIERS**

Use K-Means clustering on climate variables and assign:

Tier 1 = Low Risk

Tier 2 = Moderate Risk

Tier 3 = High Risk

Tier 4 = Severe Risk

Normalize to 0–100:

Climate Tier Score = 25, 50, 75, 100

---

2. CROP STRESS SCORE

```
DROUGHT_RULES = [
    ('VHI_mean',         'low',  'Low vegetation health (VHI < p30)'),
    ('drySpellDays',     'high', 'Long dry season (>p70 dry days)'),
    ('dry_spell_julaug', 'high', 'Reproductive stage drought (Jul-Aug dry days >p70)'),
]

FLOOD_RULES = [
    ('cumRain_mm',       'high', 'Excess seasonal rainfall (>p70)'),
    ('heavy_rain_days',  'high', 'Extreme rain events (days >50mm, >p70)'),
    ('sm_wet_days',      'high', 'Waterlogging days (SM > baseline, >p70)'),
]

HEAT_RULES = [
    ('lst_anom_augsep',  'high', 'Aug-Sep heat anomaly (LST >p70)'),
    ('gdd_surplus',      'high', 'Heat degree days above 35°C (>p70)'),
]
```

Drought Score = w1× (1 − VHI_norm) + w2 × DrySpellDays_norm + w3 × DrySpellJulAug_norm

Flood Score = w1 × CumulativeRainfall_norm + w2 × HeavyRainDays_norm + w3 × SoilMoistureWetDays_norm

Heat Score = w1 × LST_Anomaly_norm + w2 × GDD_Surplus_norm

- Flood has the clearest signal in the current data: cumulative rainfall and heavy-rain days are the strongest predictors.
- Drought is reasonable, with dry-spell days leading and VHI as a secondary input.
- Heat is the weakest family, and GDD surplus is barely correlated, so it should not dominate.

So, the weights become - 

- Drought: *w*1=0.3, *w*2=0.4, *w*3=0.3
- Flood: *w*1=0.4, *w*2=0.35, *w*3=0.25
- Heat: *w*1=0.8, *w*2=0.2

Composite Crop Stress Score = w1 × Drought Score + w2 × Flood Score + w3 × Heat Score

"composite_weights": {
"Drought_Score": 0.098,      # 0.2
"Flood_Score": 0.487            # 0.45
"Heat_Score": 0.414              # 0.35

Range: 0–100

Higher score = Higher crop stress

---

1. CREDIT / NPA RISK SCORECARD

NPA Risk Score = w1 × Climate Tier Score + w2 × Crop Stress Score + w3 × (100 − Coverage Ratio)

Range: 0–100

Interpretation:

0–30     Low Risk

30–60    Medium Risk

60–80    High Risk

80–100   Severe Risk

---

4. PREMIUM PRICING MODEL

Premium = Base Premium × (1 − Crop Stress Score × Discount Factor)

Example:

Base Premium = ₹1000

Crop Stress Score = 0.80

Discount Factor = 20%

Premium =

1000 × (1 − 0.80 × 0.20)

= ₹840

---

5. TIER-BASED PREMIUM MODEL

Resilience Score     Tier       Premium Impact

> 80                          Gold        20% Discount

60 – 80                     Silver       10% Discount

40 – 60                 Standard     Base Premium

< 40                      High Risk    15% Loading

---

6. SYNTHETIC DEFAULT LABEL

Default = 1

IF ALL CONDITIONS HOLD: Climate Tier >= High AND Crop Stress Score > 70 AND Coverage Ratio < 40%

ELSE

Default = 0

Insurance Side

Target (y):

Seasonal Minimum NDVI Anomaly

Features (X):

- Rainfall Deficit
- Consecutive Dry Days
- Temperature Anomaly
- Soil Moisture Anomaly
- VPD
- VHI

Model:

Random Forest Regressor

Credit Side

Target (y):

Synthetic Default Label

Features (X):

- Climate Tier Score
- Crop Stress Score
- Coverage Ratio
- Rainfall Deficit
- Soil Moisture
- VPD
- NDVI Anomaly

Models:

- Logistic Regression
- Random Forest Classifier
- XGBoost (optional)

Output:

Probability of Financial Distress / Default

# Premium Pricing Formula — Practice-Linked Parametric Insurance

*Core USP: premium and payout are tied to verified agroecology adoption, not just static regional risk.*

---

## The formula

```
Farmer Premium = Base Actuarial Premium × Practice Adjustment Factor × Transition Stage Factor
```

---

## Layer 1 — Base Actuarial Premium

Reflects objective climate/plot risk only — not affected by farming practice.

```
Base Premium = Sum Insured × Risk Index(region, crop)

Risk Index(region, crop) = w1·RDI + w2·CDD + w3·NDVI_anomaly + w4·HeatStress + w5·SAR_moisture

  RDI            = Rainfall Deficit Index (CHIRPS)
  CDD            = Consecutive Dry Days in key growth window (CHIRPS)
  NDVI_anomaly   = z-score vs. historical mean (MODIS)
  HeatStress     = days above threshold temp during flowering (ERA5)
  SAR_moisture   = waterlogging anomaly (Sentinel-1)

  w1..w5 calibrated via regression against historical Yield-Based claims (PMFBY backtest)
```

---

## Layer 2 — Practice Adjustment Factor

The USP layer. Discount tied to *verified* agroecology adoption tier.

| Tier | Criteria (illustrative) | Adjustment Factor |
| --- | --- | --- |
| Tier 0 — Baseline | No verified ecological practice | × 1.00 |
| Tier 1 — Transitioning | 1–2 verified practices adopted, meets "10% Rule" land coverage threshold | × 0.90 |
| Tier 2 — Partial adoption | Multiple practices + NDVI-verified soil health improvement | × 0.80 |
| Tier 3 — Full adoption | Full practice stack, verified across multiple seasons | × 0.70 |

⚠️ **These discount magnitudes are illustrative placeholders.** They need to be calibrated against backtest evidence — i.e., confirming that higher-practice-score plots actually show lower historical loss ratios in the PMFBY data — before they're pitch-ready as "validated" numbers.

### What counts as a "verified practice" — the checklist

Each practice needs a named data source, not a self-report. This is what actually gets scored:

| Practice | What it is | Verification data source |
| --- | --- | --- |
| Seed treatment (Beejamritam-style biological seed coating) | Non-synthetic seed protection at sowing | CRP geo-fenced, time-stamped photo at sowing stage |
| Reduced/zero synthetic pesticide & fertilizer use | Shift away from chemical inputs | Input purchase records (if routed through UMED/NIOS-style input shops); absence of chemical-input transactions is itself a signal |
| Intercropping / polycropping | Mixed monocots + dicots instead of single-crop rows | Sentinel-2 optical classification — spectral signature distinguishes single-crop rows from mixed planting |
| Botanical pest management (neem/chilli/garlic-based sprays) | Non-synthetic pest control | CRP photo log at application stage |
| Soil health trend | Cumulative effect of the above, over time | MODIS/Sentinel NDVI-EVI time series — multi-season trend, not a single snapshot |

A farmer's Tier is a function of how many of these are verified *and* how long they've been sustained — not a one-time checklist tick.

### Anti-gaming safeguards

Tying money to a score creates an incentive to game the score rather than genuinely adopt the practice. Three safeguards, mirroring what APCNF already runs at 1.8M-farmer scale:

1. **Multi-season verification, not a single snapshot.** A practice only counts toward a Tier once it's been verified across more than one growth stage in the same season (sowing + mid-season + pre-harvest), and ideally repeated across seasons before a farmer moves to Tier 2/3. This mirrors APCNF's requirement that CRPs photograph at brewing, sowing, *and* growth stages — a single photo is easy to stage, a consistent multi-point record is much harder to fake.
2. **Geo-fencing + timestamp cross-check.** Photos must match the registered plot's coordinates and fall within the expected phenological window (e.g. a "sowing stage" photo timestamped outside the sowing calendar gets flagged). This is the same backend cross-check APCNF's e-Rythu app runs to catch farmers claiming natural practices while still using chemical inputs.
3. **Satellite-vs-ground discrepancy triggers manual review.** If satellite data (e.g. NDVI pattern inconsistent with claimed intercropping, or no vegetation signature change consistent with reduced chemical use) disagrees with the CRP-submitted record, the plot gets flagged for manual re-verification rather than automatically accepted at face value. This is also the mechanism that keeps CRPs themselves honest — not just farmers.

**Cost implication:** this verification load is why Tier upgrades should require *sustained, cross-checked* evidence rather than a fast self-certification — it protects the actuarial basis for the discount, and it's a large part of why paying CRPs to double as verification agents (discussed separately) matters operationally, not just as a distribution nicety.

---

## Layer 3 — Transition Stage Factor

Covers the transition-period yield dip (15–20%) that a farmer on the edge can't absorb. Applies only in the first 1–2 seasons of transition.

```
Transition Stage Factor = 1 + Transition Risk Loading   (only during transition seasons)
```

Design rule: the risk loading must be smaller than the Tier 1 discount, so the farmer's net premium is still lower than baseline — while the trigger threshold for payout is *relaxed* during this window, so the product functions as the de-risker for the transition dip, not just a discount.

---

## Worked example

Assumptions: Sum Insured = ₹1,00,000; Base Premium follows PMFBY-style 2% cap.

| Farmer scenario | Base Premium | Practice Factor | Transition Factor | Final Premium | Net vs. baseline |
| --- | --- | --- | --- | --- | --- |
| Tier 0 (no adoption) | ₹2,000 | × 1.00 | × 1.00 | **₹2,000** | — |
| Tier 1, in transition | ₹2,000 | × 0.90 | × 1.05 | **₹1,890** | −5.5% |
| Tier 2, past transition | ₹2,000 | × 0.80 | × 1.00 | **₹1,600** | −20% |
| Tier 3, past transition | ₹2,000 | × 0.70 | × 1.00 | **₹1,400** | −30% |

---

## Open items for the team

1. **Calibrate Tier discount magnitudes (0.90 / 0.80 / 0.70)** against real backtest loss-ratio data — do higher-practice-score plots actually show measurably lower historical losses?
2. **Define the Practice Tier scoring rule** — exact mapping from satellite/CRP-verified data (NDVI improvement, input records, geo-tagged photos) to Tier 0–3. Needs alignment with whoever owns the practice-verification layer.
3. **Set the Transition Risk Loading value** — currently a placeholder (1.05); should be small enough that net premium stays below baseline in all transitioning scenarios.
4. **Decide the payout-side relaxation mechanism for transition seasons** — e.g. lower trigger threshold, faster payout window — needs its own formula, not yet specified here.

**PRESENTATION :** Scorecard based