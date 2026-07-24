# Mool — Parametric Crop Insurance · Vidarbha Pilot

Satellite-driven parametric crop insurance for smallholder farmers across 4 Vidarbha districts
(Yavatmal, Amravati, Chandrapur, Wardha). Triggers payouts automatically based on satellite-derived
climate indices — no claim filing, no CCE, no 6-month delay.

**Current model: `Vidarbha_ModelExperiment_v9.ipynb` — "climate-shock-first"**

---

## What v9 proves

v9 reframes the product: insure **climate shocks** (drought/flood detected from satellite), not
**yield outcomes** (which are corrupted by pests, market prices, and farmer behavior that satellites
can't see). It separates drought and flood into two independent indices instead of one composite
that cancels itself out.

Recomputing every prior version's *actual* trigger logic on the same 22-year dataset (2003–2024)
and the same PMFBY benchmark window (2018–2024):

| Version | Method | Fire rate | Precision | Recall | F1 | Basis risk |
|---|---|---|---|---|---|---|
| v5 | Percentile thresholds, 2-of-3 AND | 47% | 43% | 73% | 0.54 | 11% |
| v6 | v5 + SMAP soil moisture rule | 53% | 43% | 74% | 0.54 | 10% |
| v7/v8 | Entropy-weighted CHF composite | 46% | 45% | 35% | 0.39 | 25% |
| **v9** | **Separate Drought + Flood indices** | **39%** | **62%** | **61%** | **0.62** | **15%** |

**v9 wins on F1, precision, and fire-rate efficiency.** v5/v6 have higher recall but fire on
nearly half of all RC-years (unaffordable premium load). v7/v8's single composite index has the
*worst* F1 of all versions — proof that mixing drought and flood signals into one number actively
hurts, since rain is "good" for drought and "bad" for flood simultaneously.

Full reproducible comparison: `scripts/version_comparison.py` → `data/processed/version_comparison_metrics.csv`.

---

## Model evolution (v4 → v9)

All prior notebooks, their outputs, and superseded docs are preserved in `archive/` for full
traceability — nothing was deleted, only superseded.

| Version | Core idea | Where |
|---|---|---|
| v4 | Multi-peril OR-logic backtest, first 4-district version | `archive/notebooks/Vidarbha_ModelExperiment_v4.ipynb` |
| v5 | Fixed OR-inflation with 2-of-3 AND logic, IMD rainfall standards | `archive/notebooks/Vidarbha_ModelExperiment_v5.ipynb` |
| v6 | + SMAP soil moisture, SAR, ET anomaly features | `archive/notebooks/Vidarbha_ModelExperiment_v6.ipynb` |
| v7 | Composite Crop Health Factor (CHF), entropy-weighted, yield-calibrated | `archive/notebooks/Vidarbha_ModelExperiment_v7.ipynb` |
| v8 | v7 + 23-year satellite history, corrected DES APY data, PMFBY calibration | `archive/notebooks/Vidarbha_ModelExperiment_v8.ipynb` |
| **v9** | **Separate Drought/Flood indices, climate-severity calibration, practice-linked pricing concept** | **`Vidarbha_ModelExperiment_v9.ipynb`** (root, current) |

---

## v9 architecture

```
DROUGHT INDEX (DI)  = weighted z-score of:
                       LST anomaly (35%) + FAPAR (25%) + NDVI Aug-Sep (15%)
                       + Jun-Jul rainfall (15%) + dry-spell days (10%)

FLOOD INDEX (FI)     = weighted z-score of:
                       Aug-Sep rainfall (50%) + heavy rain days (30%) + waterlogging days (20%)
─────────────────────────────────────────────────────────────────────────────
TRIGGER              : DI < strike (p28)  OR  FI > strike (p85)
PAYOUT               : graduated 20%→100% of sum insured between strike and exit
CALIBRATION          : historical severity distribution, cross-checked vs PMFBY + APY
                        (NOT trained/fit against either — avoids circular calibration)
```

Practice-linked pricing (drip irrigation, polycropping, APCNF discounts) is prototyped via a
resilience score built from NDVI stability/recovery patterns — see notebook section I.
Field-level (not just revenue-circle-level) practice detection is feasible but needs 10m Sentinel-2
+ Fields of The World boundaries — see section N and "Next steps" below.

---

## Data pipeline

```
PMFBY dashboard  →  scripts/pmfby_scraper.py  (+ per-district variants)
                                    │
Google Earth Engine  →  scripts/extract_rc_features_v2.py       (2018-2025 core features)
                      →  scripts/extract_extra_features.py      (ET, SMAP, SAR)
                      →  scripts/extract_chf_features.py        (FAPAR, sub-windows)
                      →  scripts/extract_historical_features.py (2003-2017 backfill, 20 threads)
                                    │
                       scripts/merge_historical.py
                                    │
              data/processed/all_districts_23yr_features.csv   (22 years × 4 districts × ~280 RCs)
                                    │
                     + data/processed/apy_district_yields_v2.csv (official DES yields, 2000-2022)
                                    │
                     Vidarbha_ModelExperiment_v9.ipynb  →  vidarbha_outputs/
```

---

## Notebooks

| Notebook | What it does | Status |
|---|---|---|
| `DataIngestion_Resilient_Agro.ipynb` | Original GEE ingestion for Karnal + Ratnagiri pilot | Deprecated |
| `Vidarbha_Backtest_DataCollection.ipynb` | GEE data pull for 4 Vidarbha district towns | Reference |
| `Yavatmal_RC_DataCollection.ipynb` | GEE data pull for 110 Yavatmal revenue-circle centroids | Reference |
| `Vidarbha_ModelExperimentv2_yug.ipynb` | Colleague's parallel feature-weighting experiment (see `data/processed/feature_weight_analysis.json`) | Reference |
| `archive/notebooks/Vidarbha_ModelExperiment_v4.ipynb` … `_v8.ipynb` | Full model evolution history | Archived |
| **`Vidarbha_ModelExperiment_v9.ipynb`** | **Climate-shock-first model — the current deliverable** | **CURRENT** |

---

## Scripts

| Script | What it does |
|---|---|
| `scripts/pmfby_scraper.py` | Playwright scraper for PMFBY dashboard → IU-level kharif data |
| `scripts/geocode_revenue_circles.py` | Geocodes revenue circles via Nominatim |
| `scripts/extract_rc_features_v2.py` | GEE extraction: core phenological-window features |
| `scripts/extract_extra_features.py` | GEE extraction: MODIS ET anomaly, SMAP soil moisture, Sentinel-1 SAR |
| `scripts/extract_chf_features.py` | GEE extraction: FAPAR + drought/flood sub-window features |
| `scripts/extract_historical_features.py` | GEE extraction: 2003-2017 backfill (20-thread parallel), extends dataset to 22 years |
| `scripts/merge_historical.py` | Merges historical + current features into one 23-year dataset |
| `scripts/version_comparison.py` | Recomputes v5/v6/v7-v8/v9 trigger logic on identical data for fair comparison |
| `scripts/test_sentinel2_sar.py` | Live GEE feasibility test: Sentinel-2 cloud cover + SAR texture in Kharif season |

---

## Key data files

| File | Description |
|---|---|
| `data/processed/all_districts_23yr_features.csv` | **Main feature set**: 22 years × 4 districts × ~280 RCs |
| `data/processed/apy_district_yields_v2.csv` | Official DES APY yields, 18 Kharif crops, 2000-2022 |
| `data/processed/ftw_district_field_counts.csv` | Fields of The World field-boundary counts per district (feasibility test) |
| `data/processed/s2_sar_feasibility_test.csv` | Sentinel-2/SAR cloud-cover + texture feasibility test results |
| `data/processed/version_comparison_metrics.csv` | v5-v9 rigorous comparison metrics |
| `data/raw/pmfby_*_iu_kharif.csv` | Per-district PMFBY IU-level kharif claims data |

---

## Next steps (not yet built)

1. **Field-level zonal stats** — re-run satellite extraction using Fields of The World (FTW)
   10m field polygons instead of 5km circular RC buffers. Confirmed feasible: FTW has 800K-3.2M
   field polygons per district, real farm-shaped geometry (see notebook section N).
2. **Sentinel-2 as supplementary signal** — within-field NDVI variance (0.13-0.20) is a genuine
   polycropping/irrigation proxy, but usable in only ~30-40% of Kharif scenes due to monsoon cloud
   cover. Use as a confirmatory layer alongside SAR (which has full cloud-free coverage), not a
   primary feed.
3. **Practice-linked pricing v2** — combine field-level FTW boundaries + S2 texture + SAR to build
   a real per-farm resilience score (current v9 RC-level proxy shows only a weak 2pp fire-rate
   difference between tiers — too blurry at 5km scale to be commercially meaningful).

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install earthengine-api pandas numpy scipy scikit-learn matplotlib seaborn openpyxl jupyter duckdb

# Authenticate GEE (one time)
earthengine authenticate
```

GEE project used: `earth-mrv`

---

## Team

Mool · GCL 2026 · Parametric Insurance Track
See `docs/Team_Hub.md` for full project brief and `docs/Stakeholder_Memo.md` for the business model.
