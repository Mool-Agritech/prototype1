# Mool — Parametric Crop Insurance · Vidarbha Pilot

Satellite-driven parametric crop insurance for smallholder farmers in Yavatmal district, Vidarbha (Maharashtra).  
The product triggers payouts automatically based on GEE satellite indices — no claim filing, no CCE, no 6-month delay.

---

## What this proves

| Metric | Result |
|---|---|
| PMFBY stress events caught | **95%** recall — we rarely miss what PMFBY catches |
| Added coverage (PMFBY paid ₹0, we fire) | **31%** of all RC×years — the drought & localized events CCE misses |
| Basis risk vs PMFBY | **2%** — near-zero misses of PMFBY-caught events |
| 2023 drought (PMFBY rate_yield = 0.3%) | **62 revenue circles** correctly flagged by satellite |
| 2025 nowcast (kharif in progress) | **78% of RCs** have an active trigger (flood-dominant season) |

---

## Data pipeline

```
PMFBY dashboard  →  scripts/pmfby_scraper.py          →  data/raw/pmfby_yavatmal_iu_kharif.csv
                                                                        │
                     scripts/geocode_revenue_circles.py  →  data/processed/yavatmal_rc_coords.csv
                                                                        │
Google Earth Engine →  scripts/extract_rc_features_v1.py  →  data/processed/yavatmal_rc_features_v1.csv
                    →  scripts/extract_rc_features_v2.py  →  data/processed/yavatmal_rc_features_v2.csv
                                                                        │
                                                         join PMFBY + satellite
                                                                        │
                                                         data/processed/yavatmal_rc_model_ready_v2.csv
                                                                        │
                                                         Vidarbha_ModelExperiment.ipynb  →  vidarbha_outputs/
```

---

## Notebooks

Run these in order from the repo root (so relative paths to `data/` resolve correctly).

| Notebook | What it does | Status |
|---|---|---|
| `DataIngestion_Resilient_Agro.ipynb` | Original GEE ingestion for Karnal + Ratnagiri pilot | Deprecated |
| `Vidarbha_Backtest_DataCollection.ipynb` | GEE data pull for 4 Vidarbha district towns | Superseded |
| `Yavatmal_RC_DataCollection.ipynb` | GEE data pull for 110 Yavatmal revenue-circle centroids | Reference |
| **`Vidarbha_ModelExperiment.ipynb`** | **Multi-peril backtest + 2025 nowcast — the main deliverable** | **CURRENT** |

---

## Scripts

| Script | What it does |
|---|---|
| `scripts/pmfby_scraper.py` | Playwright scraper for PMFBY dashboard → IU-level kharif data |
| `scripts/geocode_revenue_circles.py` | Geocodes 110 revenue circles via Nominatim |
| `scripts/extract_rc_features_v1.py` | GEE extraction: 13 seasonal satellite features per RC×year |
| `scripts/extract_rc_features_v2.py` | GEE extraction: adds 8 phenological-window features (CURRENT) |

To re-run the extraction from scratch:
```bash
source .venv/bin/activate
python3 -u scripts/extract_rc_features_v2.py 2>&1 | tee logs/extract_v2_log.txt
```

---

## Key data files

| File | Description |
|---|---|
| `data/raw/pmfby_yavatmal_iu_kharif.csv` | 498 IU-level PMFBY rows, Yavatmal, Kharif 2021–2025 |
| `data/raw/PMFBY Insurance Data - Vidarbha Crisis Districts.xlsx` | District-level PMFBY benchmark (Yavatmal, Wardha, Akola, Chandrapur) |
| `data/processed/yavatmal_rc_coords.csv` | Lat/lon for 110 revenue-circle centroids |
| `data/processed/yavatmal_rc_features_v2.csv` | 21 satellite features × 550 RC×year obs |
| **`data/processed/yavatmal_rc_model_ready_v2.csv`** | **Model input: satellite features + PMFBY per-peril loss ratios** |

---

## Trigger architecture (model)

```
DROUGHT   : VHI < p30   OR  drySpellDays > p70  OR  dry_spell_julaug > p70
FLOOD     : cumRain > p70  OR  heavy_rain_days > p70  OR  sm_wet_days > p70
HEAT      : lst_anom_augsep > p70  OR  gdd_surplus > p70
─────────────────────────────────────────────────────────
PAYOUT    : ANY trigger fires  →  automatic payout
```

Thresholds are **percentile-based from satellite distributions only** — no PMFBY data is used to calibrate triggers.  
PMFBY is the comparison benchmark, not the training target.

---

## Current outputs (`vidarbha_outputs/`)

| File | Description |
|---|---|
| `satellite_distributions_v4.png` | Feature distributions + trigger thresholds per year |
| `backtest_coverage_v4.png` | Per-RC coverage map: aligned / value-add / basis risk / quiet |
| `coverage_summary_v4.png` | Year-level stacked bar + value-add peril breakdown |
| `nowcast_dashboard_v4.png` | 2025 kharif nowcast — per-peril trigger maps + year comparison |
| `nowcast_2025_v4.csv` | Per-RC 2025 trigger status and satellite scores |

Older output versions are in `vidarbha_outputs/archive/`.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install earthengine-api pandas numpy scipy scikit-learn matplotlib seaborn openpyxl jupyter

# Authenticate GEE (one time)
earthengine authenticate
```

GEE project used: `earth-mrv`

---

## Team

Mool · GCL 2026 · Parametric Insurance Track  
See `docs/Team_Hub.md` for full project brief and `docs/Stakeholder_Memo.md` for the business model.
