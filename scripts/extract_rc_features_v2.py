"""
extract_rc_features_v2.py
─────────────────────────
Adds 8 new phenological-window features to the existing yavatmal_rc_features.csv.
Checkpoints every 10 rows.  Reads existing progress from yavatmal_rc_features_v2_partial.csv.

New features:
  june_rain_mm       – CHIRPS Jun 1-15 total (prevented-sowing proxy)
  oct_rain_mm        – CHIRPS Oct 1-31 total (post-harvest / cotton quality proxy)
  heavy_rain_days    – Days with CHIRPS >50mm (flooding/waterlogging proxy)
  dry_spell_julaug   – Dry days (<2mm) Jul 20-Aug 31 (reproductive-stage drought)
  lst_anom_augsep    – LST anomaly Aug-Sep vs 10-yr baseline (anthesis heat stress)
  sm_wet_days        – Days SM > baseline mean (waterlogging days)
  gdd_surplus        – Sum of max(0, tmax_C - 35) during kharif vs baseline (heat stress)
  ndvi_slow_greenup  – # MODIS 8-day images in Jun-Jul where NDVI < 0.3 (green-up delay)

Outputs:
  yavatmal_rc_features_v2.csv      – original 13 cols + 8 new cols (550 rows)
  yavatmal_rc_model_ready_v2.csv   – above + per-peril PMFBY monetary loss ratios
"""

import ee
import pandas as pd
import numpy as np
import time
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
GEE_PROJECT = 'earth-mrv'
KHARIF_YEARS = [2021, 2022, 2023, 2024, 2025]
BUFFER_M = 5000
SCALE_M  = 1000
PARTIAL  = Path('data/processed/yavatmal_rc_features_v2_partial.csv')
OUT_V2   = Path('data/processed/yavatmal_rc_features_v2.csv')
OUT_MODEL= Path('data/processed/yavatmal_rc_model_ready_v2.csv')

# ── GEE auth ──────────────────────────────────────────────────────────────────
try:
    ee.Initialize(project=GEE_PROJECT)
    print('GEE initialised.')
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)
    print('GEE authenticated + initialised.')

# ── Pre-compute baselines (10-yr, once) ───────────────────────────────────────
print('Building new baselines...')

# LST baseline for Aug-Sep only
LST_BASE_AUGSEP = (ee.ImageCollection('MODIS/061/MOD11A2')
                     .select('LST_Day_1km')
                     .filter(ee.Filter.calendarRange(8, 9, 'month'))
                     .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
                     .mean().multiply(0.02).subtract(273.15))

# SM baseline mean (full kharif)
SM_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
             .select('volumetric_soil_water_layer_1')
             .filter(ee.Filter.calendarRange(6, 10, 'month'))
             .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
             .mean())

# GDD baseline: mean of sum(max(0, tmax_C - 35)) per kharif season
# We approximate: map each image → max(0, tmax - 308.15 K), then sum across baseline years
# GDD_BASE_IMG = mean daily (tmax-35)+ across all baseline kharif days → multiply by ~153 season days
ERA5_KHARIF_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                      .select('temperature_2m_max')
                      .filter(ee.Filter.calendarRange(6, 10, 'month'))
                      .filter(ee.Filter.date('2016-01-01', '2026-01-01')))
# Mean daily heat above 35 °C (in Kelvin: 35°C = 308.15K)
GDD_BASE_DAILY_MEAN = (ERA5_KHARIF_BASE
                         .map(lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat'))
                         .mean())  # average daily heat-above-35 across baseline

print('Baselines ready.')


def extract_new_features(lat, lon, year):
    pt  = ee.Geometry.Point([lon, lat])
    aoi = pt.buffer(BUFFER_M)

    def red(img, scale=SCALE_M):
        return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)

    # ── 1. june_rain_mm: CHIRPS Jun 1-15 ─────────────────────────────────────
    chirps_june = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .select('precipitation')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-06-16')))
    june_rain = red(chirps_june.sum())

    # ── 2. oct_rain_mm: CHIRPS Oct 1-31 ──────────────────────────────────────
    chirps_oct = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                    .select('precipitation')
                    .filter(ee.Filter.date(f'{year}-10-01', f'{year}-11-01')))
    oct_rain = red(chirps_oct.sum())

    # ── 3. heavy_rain_days: days with >50mm (flood proxy) ────────────────────
    chirps_full = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .select('precipitation')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
    heavy_days = red(chirps_full.map(lambda i: i.gt(50).rename('heavy')).sum())

    # ── 4. dry_spell_julaug: dry days Jul 20-Aug 31 ───────────────────────────
    chirps_julaug = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                       .select('precipitation')
                       .filter(ee.Filter.date(f'{year}-07-20', f'{year}-09-01')))
    dry_julaug = red(chirps_julaug.map(lambda i: i.lt(2).rename('dry')).sum())

    # ── 5. lst_anom_augsep: LST anomaly Aug-Sep ───────────────────────────────
    lst_augsep = (ee.ImageCollection('MODIS/061/MOD11A2')
                    .select('LST_Day_1km')
                    .filter(ee.Filter.date(f'{year}-08-01', f'{year}-10-01'))
                    .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_anom_augsep = lst_augsep.mean().subtract(LST_BASE_AUGSEP)
    lst_anom_augsep_val = lst_anom_augsep.reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # ── 6. sm_wet_days: days SM > baseline mean ───────────────────────────────
    sm_col = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                .select('volumetric_soil_water_layer_1')
                .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
    sm_wet = red(sm_col.map(lambda i: i.gt(SM_BASE).rename('wet')).sum())

    # ── 7. gdd_surplus: season GDD above 35°C vs baseline ────────────────────
    era5_season = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                     .select('temperature_2m_max')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
    # Mean daily heat-above-35 this season
    gdd_season_daily = era5_season.map(
        lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat')
    ).mean()
    gdd_surplus_img = gdd_season_daily.subtract(GDD_BASE_DAILY_MEAN).rename('gdd')
    gdd_surplus_val = gdd_surplus_img.reduceRegion(ee.Reducer.mean(), aoi, SCALE_M, maxPixels=1e7)

    # ── 8. ndvi_slow_greenup: MODIS 8-day Jun-Jul images with NDVI < 0.3 ─────
    ndvi_juljul = (ee.ImageCollection('MODIS/061/MOD13Q1')
                     .select('NDVI')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-08-01'))
                     .map(lambda i: i.multiply(0.0001)))
    slow_greenup = ndvi_juljul.map(lambda i: i.lt(0.3).rename('slow')).sum()
    slow_greenup_val = slow_greenup.reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)

    result = ee.Dictionary({
        'june_rain_mm':      june_rain.get('precipitation'),
        'oct_rain_mm':       oct_rain.get('precipitation'),
        'heavy_rain_days':   heavy_days.get('heavy'),
        'dry_spell_julaug':  dry_julaug.get('dry'),
        'lst_anom_augsep':   lst_anom_augsep_val.get('LST_Day_1km'),
        'sm_wet_days':       sm_wet.get('wet'),
        'gdd_surplus':       gdd_surplus_val.get('gdd'),
        'ndvi_slow_greenup': slow_greenup_val.get('slow'),
    })
    return result.getInfo()


# ── Main loop ─────────────────────────────────────────────────────────────────
existing_v1 = pd.read_csv('data/processed/yavatmal_rc_features_v1.csv')
coords_df   = existing_v1[['taluka', 'revenue_circle', 'lat', 'lon',
                            'year', 'geocode_flag']].copy()

if PARTIAL.exists():
    done_df   = pd.read_csv(PARTIAL)
    done_keys = set(zip(done_df['revenue_circle'], done_df['year']))
    print(f'Resuming — {len(done_df)} rows already done.')
else:
    done_df   = pd.DataFrame()
    done_keys = set()

rows  = []
total = len(coords_df)
done  = len(done_keys)
t0    = time.time()

for i, row_s in coords_df.iterrows():
    rc     = row_s['revenue_circle']
    taluka = row_s['taluka']
    lat    = row_s['lat']
    lon    = row_s['lon']
    year   = row_s['year']

    if (rc, year) in done_keys:
        continue

    done += 1
    try:
        feats = extract_new_features(lat, lon, year)
        row = {'taluka': taluka, 'revenue_circle': rc, 'year': year}
        row.update(feats)
        rows.append(row)
        status = '✓'
    except Exception as e:
        rows.append({'taluka': taluka, 'revenue_circle': rc, 'year': year,
                     'error_v2': str(e)[:200]})
        status = f'✗ {str(e)[:80]}'

    elapsed  = time.time() - t0
    eta_min  = (elapsed / done) * (total - done) / 60 if done > 0 else 0
    print(f'[{done:03d}/{total}] {done/total*100:.0f}%  {taluka}/{rc} {year}: {status}  '
          f'(elapsed {elapsed/60:.1f}m  ETA {eta_min:.0f}m)', flush=True)

    if done % 10 == 0:
        df_partial = pd.concat([done_df, pd.DataFrame(rows)], ignore_index=True)
        df_partial.to_csv(PARTIAL, index=False)
        print(f'  → checkpoint saved ({len(df_partial)} rows)', flush=True)

# ── Save new features ─────────────────────────────────────────────────────────
new_feats_df = pd.concat([done_df, pd.DataFrame(rows)], ignore_index=True)
new_feats_df.to_csv(PARTIAL, index=False)
print(f'\n✓ New features: {len(new_feats_df)} rows')

# ── Merge with existing v1 features ──────────────────────────────────────────
merge_cols = ['taluka', 'revenue_circle', 'year']
v2 = existing_v1.merge(
    new_feats_df.drop(columns=['error_v2'], errors='ignore'),
    on=merge_cols, how='left')
v2.to_csv(OUT_V2, index=False)
print(f'✓ Full v2 feature set: {len(v2)} rows, {len(v2.columns)} cols → {OUT_V2}')

# ── Join PMFBY with per-peril monetary loss ratios ────────────────────────────
print('\nJoining PMFBY (monetary loss ratios)...')
pmfby = pd.read_csv('data/raw/pmfby_yavatmal_iu_kharif.csv')

# All claim columns are in Lac (₹100,000), sum_insured_rs is in absolute Rupees
claim_cols = ['claim_total', 'claim_yield_based', 'claim_localized',
              'claim_prevented_sowing', 'claim_post_harvest',
              'claim_midterm', 'claim_wbcis']
for c in claim_cols + ['sum_insured_rs', 'farmers', 'area_insured_hect']:
    pmfby[c] = pd.to_numeric(pmfby[c], errors='coerce')

pmfby_agg = (pmfby.groupby(['taluka', 'revenue_circle', 'year'])
                   .agg(
                       farmers_total       =('farmers', 'sum'),
                       area_ha             =('area_insured_hect', 'sum'),
                       sum_insured_rs      =('sum_insured_rs', 'sum'),
                       claim_total_lac     =('claim_total', 'sum'),
                       claim_yield_lac     =('claim_yield_based', 'sum'),
                       claim_local_lac     =('claim_localized', 'sum'),
                       claim_prevented_lac =('claim_prevented_sowing', 'sum'),
                       claim_postharvest_lac=('claim_post_harvest', 'sum'),
                       claim_midterm_lac   =('claim_midterm', 'sum'),
                   )
                   .reset_index())

# Monetary loss ratios (claim in Rs / sum insured in Rs)
# claim_X_lac * 1e5 = claim in Rs;  sum_insured_rs already in Rs
denom = pmfby_agg['sum_insured_rs'].replace(0, np.nan)
pmfby_agg['rate_total']      = (pmfby_agg['claim_total_lac']      * 1e5) / denom
pmfby_agg['rate_yield']      = (pmfby_agg['claim_yield_lac']      * 1e5) / denom
pmfby_agg['rate_local']      = (pmfby_agg['claim_local_lac']      * 1e5) / denom
pmfby_agg['rate_prevented']  = (pmfby_agg['claim_prevented_lac']  * 1e5) / denom
pmfby_agg['rate_postharvest']= (pmfby_agg['claim_postharvest_lac']* 1e5) / denom
pmfby_agg['rate_midterm']    = (pmfby_agg['claim_midterm_lac']    * 1e5) / denom

v2['revenue_circle'] = v2['revenue_circle'].str.strip()
pmfby_agg['revenue_circle']  = pmfby_agg['revenue_circle'].str.strip()

model_v2 = v2.merge(
    pmfby_agg[['taluka', 'revenue_circle', 'year',
               'farmers_total', 'area_ha', 'sum_insured_rs',
               'claim_total_lac', 'claim_yield_lac', 'claim_local_lac',
               'claim_prevented_lac', 'claim_postharvest_lac', 'claim_midterm_lac',
               'rate_total', 'rate_yield', 'rate_local',
               'rate_prevented', 'rate_postharvest', 'rate_midterm']],
    on=['taluka', 'revenue_circle', 'year'], how='left')

model_v2.to_csv(OUT_MODEL, index=False)

n_match = model_v2['rate_total'].notna().sum()
print(f'✓ Model-ready v2: {len(model_v2)} rows, {n_match} with rate_total')
print(f'  Columns: {list(model_v2.columns)}')
print(f'  Saved → {OUT_MODEL}')

# Quick sanity check
print('\n── Rate statistics (where sum_insured > 0) ──')
for col in ['rate_total', 'rate_yield', 'rate_local', 'rate_prevented']:
    vals = model_v2[col].dropna()
    if len(vals) > 0:
        print(f'  {col:20s}  mean={vals.mean():.4f}  max={vals.max():.4f}  nonzero={( vals>0).sum()}')
