"""
extract_rc_features_v3.py
─────────────────────────
Extends the feature dataset to cover Kharif 2018-2025 (from 2021-2025).

Strategy:
  - Loads existing yavatmal_rc_features_v2.csv as the "already done" rows
  - Only calls GEE for the 3 new years: 2018, 2019, 2020
  - Extracts ALL 21 features (v1 + v2 combined) in a single GEE call per RC-year
  - Checkpoints every 10 rows to yavatmal_rc_features_v3_partial.csv
  - Outputs:
      data/processed/yavatmal_rc_features_v3.csv      — 880 rows (110 RCs × 8 years)
      data/processed/yavatmal_rc_model_ready_v3.csv   — above + PMFBY monetary loss ratios

Usage:
    source .venv/bin/activate
    python3 -u scripts/extract_rc_features_v3.py 2>&1 | tee logs/extract_v3_log.txt
"""

import ee
import pandas as pd
import numpy as np
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
GEE_PROJECT    = 'earth-mrv'
NEW_YEARS      = [2018, 2019, 2020]     # only these need GEE calls
ALL_YEARS      = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
BUFFER_M       = 5000
SCALE_M        = 1000
KHARIF_START   = '06-01'
KHARIF_END     = '10-31'
EXISTING_V2    = Path('data/processed/yavatmal_rc_features_v2.csv')
PARTIAL        = Path('data/processed/yavatmal_rc_features_v3_partial.csv')
OUT_FEATURES   = Path('data/processed/yavatmal_rc_features_v3.csv')
OUT_MODEL      = Path('data/processed/yavatmal_rc_model_ready_v3.csv')
COORDS_FILE    = Path('data/processed/yavatmal_rc_coords.csv')
PMFBY_FILE     = Path('data/raw/pmfby_yavatmal_iu_kharif.csv')

# ── GEE auth ──────────────────────────────────────────────────────────────────
try:
    ee.Initialize(project=GEE_PROJECT)
    print('GEE initialised.')
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)
    print('GEE authenticated + initialised.')

# ── Pre-compute baselines (once, 2016–2026 window) ────────────────────────────
# Using a fixed historical window keeps anomalies consistent across all years
BASE_WINDOW = ('2016-01-01', '2026-01-01')
print('Building baseline images...')

ERA5_TMAX_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                    .select('temperature_2m_max')
                    .filter(ee.Filter.calendarRange(6, 10, 'month'))
                    .filter(ee.Filter.date(*BASE_WINDOW))
                    .mean())

NDVI_BASE = (ee.ImageCollection('MODIS/061/MOD13Q1')
               .select('NDVI')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date(*BASE_WINDOW))
               .median().multiply(0.0001))

LST_BASE = (ee.ImageCollection('MODIS/061/MOD11A2')
              .select('LST_Day_1km')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .mean().multiply(0.02).subtract(273.15))

SM_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
             .select('volumetric_soil_water_layer_1')
             .filter(ee.Filter.calendarRange(6, 10, 'month'))
             .filter(ee.Filter.date(*BASE_WINDOW))
             .mean())

NDVI_MIN = (ee.ImageCollection('MODIS/061/MOD13Q1')
              .select('NDVI')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .min().multiply(0.0001))
NDVI_MAX = (ee.ImageCollection('MODIS/061/MOD13Q1')
              .select('NDVI')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .max().multiply(0.0001))
LST_MIN  = (ee.ImageCollection('MODIS/061/MOD11A2')
              .select('LST_Day_1km')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .min().multiply(0.02).subtract(273.15))
LST_MAX  = (ee.ImageCollection('MODIS/061/MOD11A2')
              .select('LST_Day_1km')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .max().multiply(0.02).subtract(273.15))

LST_BASE_AUGSEP = (ee.ImageCollection('MODIS/061/MOD11A2')
                     .select('LST_Day_1km')
                     .filter(ee.Filter.calendarRange(8, 9, 'month'))
                     .filter(ee.Filter.date(*BASE_WINDOW))
                     .mean().multiply(0.02).subtract(273.15))

GDD_BASE_DAILY_MEAN = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                         .select('temperature_2m_max')
                         .filter(ee.Filter.calendarRange(6, 10, 'month'))
                         .filter(ee.Filter.date(*BASE_WINDOW))
                         .map(lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat'))
                         .mean())

print('Baselines ready.')


def extract_all_features(lat, lon, year):
    """Extract all 21 features (v1 + v2) for a single RC-year."""
    pt    = ee.Geometry.Point([lon, lat])
    aoi   = pt.buffer(BUFFER_M)
    start = f'{year}-{KHARIF_START}'
    end   = f'{year}-{KHARIF_END}'

    def red(img, scale=SCALE_M):
        return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)

    # ── V1 FEATURES ───────────────────────────────────────────────────────────

    # CHIRPS: cumulative rain + dry spell days
    chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                .select('precipitation')
                .filter(ee.Filter.date(start, end)))
    cumRain  = red(chirps.sum())
    dry_days = red(chirps.map(lambda i: i.lt(2).rename('dry')).sum())

    # SPI-30 proxy
    chirps_base_mean = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                          .select('precipitation')
                          .filter(ee.Filter.calendarRange(6, 10, 'month'))
                          .filter(ee.Filter.date(*BASE_WINDOW))
                          .sum())
    chirps_base_std  = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                          .select('precipitation')
                          .filter(ee.Filter.calendarRange(6, 10, 'month'))
                          .filter(ee.Filter.date(*BASE_WINDOW))
                          .reduce(ee.Reducer.stdDev()))
    spi_img = (chirps.sum()
               .subtract(chirps_base_mean)
               .divide(chirps_base_std.rename('precipitation').add(1e-6))
               .rename('SPI30'))
    spi_val = red(spi_img)

    # ERA5 tmax
    era5 = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
              .select('temperature_2m_max')
              .filter(ee.Filter.date(start, end)))
    tmax_mean = red(era5.mean())
    tmax_anom = red(era5.mean().subtract(ERA5_TMAX_BASE))

    # ERA5 soil moisture
    sm_col = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                .select('volumetric_soil_water_layer_1')
                .filter(ee.Filter.date(start, end)))
    sm_mean = red(sm_col.mean())
    sm_anom = red(sm_col.mean().subtract(SM_BASE))

    # MODIS NDVI
    ndvi_col = (ee.ImageCollection('MODIS/061/MOD13Q1')
                  .select('NDVI')
                  .filter(ee.Filter.date(start, end))
                  .map(lambda i: i.multiply(0.0001)))
    ndvi_peak = ndvi_col.max().reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)
    ndvi_mean = ndvi_col.mean().reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)
    ndvi_anom = ndvi_col.mean().subtract(NDVI_BASE).reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)

    # MODIS LST
    lst_col = (ee.ImageCollection('MODIS/061/MOD11A2')
                 .select('LST_Day_1km')
                 .filter(ee.Filter.date(start, end))
                 .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_mean = lst_col.mean().reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)
    lst_anom = lst_col.mean().subtract(LST_BASE).reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # VHI
    ndvi_now = ndvi_col.mean()
    lst_now  = lst_col.mean()
    vci = ndvi_now.subtract(NDVI_MIN).divide(NDVI_MAX.subtract(NDVI_MIN).add(1e-6))
    tci = LST_MAX.subtract(lst_now).divide(LST_MAX.subtract(LST_MIN).add(1e-6))
    vhi = vci.multiply(0.5).add(tci.multiply(0.5)).rename('VHI')
    vhi_val = vhi.reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # ── V2 FEATURES ───────────────────────────────────────────────────────────

    # june_rain_mm: CHIRPS Jun 1-15
    june_rain = red((ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                       .select('precipitation')
                       .filter(ee.Filter.date(f'{year}-06-01', f'{year}-06-16'))).sum())

    # oct_rain_mm: CHIRPS Oct 1-31
    oct_rain = red((ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                      .select('precipitation')
                      .filter(ee.Filter.date(f'{year}-10-01', f'{year}-11-01'))).sum())

    # heavy_rain_days: days >50mm
    chirps_full = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .select('precipitation')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
    heavy_days = red(chirps_full.map(lambda i: i.gt(50).rename('heavy')).sum())

    # dry_spell_julaug: dry days Jul 20-Aug 31 (reproductive stage)
    chirps_julaug = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                       .select('precipitation')
                       .filter(ee.Filter.date(f'{year}-07-20', f'{year}-09-01')))
    dry_julaug = red(chirps_julaug.map(lambda i: i.lt(2).rename('dry')).sum())

    # lst_anom_augsep: LST anomaly Aug-Sep
    lst_augsep = (ee.ImageCollection('MODIS/061/MOD11A2')
                    .select('LST_Day_1km')
                    .filter(ee.Filter.date(f'{year}-08-01', f'{year}-10-01'))
                    .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_anom_augsep_val = lst_augsep.mean().subtract(LST_BASE_AUGSEP).reduceRegion(
        ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # sm_wet_days: days SM > baseline mean
    sm_wet = red((ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                    .select('volumetric_soil_water_layer_1')
                    .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
                 .map(lambda i: i.gt(SM_BASE).rename('wet')).sum())

    # gdd_surplus: excess heat-degree-days above 35°C vs baseline
    era5_season = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                     .select('temperature_2m_max')
                     .filter(ee.Filter.date(start, end)))
    gdd_season_daily = era5_season.map(
        lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat')
    ).mean()
    gdd_surplus_val = gdd_season_daily.subtract(GDD_BASE_DAILY_MEAN).rename('gdd').reduceRegion(
        ee.Reducer.mean(), aoi, SCALE_M, maxPixels=1e7)

    # ndvi_slow_greenup: MODIS 8-day Jun-Jul images with NDVI < 0.3
    ndvi_juljul = (ee.ImageCollection('MODIS/061/MOD13Q1')
                     .select('NDVI')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-08-01'))
                     .map(lambda i: i.multiply(0.0001)))
    slow_greenup_val = ndvi_juljul.map(lambda i: i.lt(0.3).rename('slow')).sum().reduceRegion(
        ee.Reducer.mean(), aoi, 500, maxPixels=1e7)

    result = ee.Dictionary({
        # V1
        'cumRain_mm':      cumRain.get('precipitation'),
        'SPI30_mean':      spi_val.get('SPI30'),
        'drySpellDays':    dry_days.get('dry'),
        'tmax_K_mean':     tmax_mean.get('temperature_2m_max'),
        'tmax_anom_K':     tmax_anom.get('temperature_2m_max'),
        'SM_mean':         sm_mean.get('volumetric_soil_water_layer_1'),
        'SM_anom':         sm_anom.get('volumetric_soil_water_layer_1'),
        'NDVI_peak':       ndvi_peak.get('NDVI'),
        'NDVI_mean':       ndvi_mean.get('NDVI'),
        'NDVI_anom':       ndvi_anom.get('NDVI'),
        'LST_mean_C':      lst_mean.get('LST_Day_1km'),
        'LST_anom_C':      lst_anom.get('LST_Day_1km'),
        'VHI_mean':        vhi_val.get('VHI'),
        # V2
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
coords_df = pd.read_csv(COORDS_FILE).dropna(subset=['lat', 'lon'])
existing_v2 = pd.read_csv(EXISTING_V2)
print(f'Loaded existing v2: {len(existing_v2)} rows (years {sorted(existing_v2.year.unique())})')

# Load partial progress for new years
if PARTIAL.exists():
    partial_df = pd.read_csv(PARTIAL)
    done_keys  = set(zip(partial_df['revenue_circle'], partial_df['year']))
    print(f'Resuming — {len(partial_df)} new-year rows already done.')
else:
    partial_df = pd.DataFrame()
    done_keys  = set()

new_rows = []
tasks    = [(row.revenue_circle, row.taluka, row.lat, row.lon, yr)
            for _, row in coords_df.iterrows()
            for yr in NEW_YEARS]
total = len(tasks)
done  = len(done_keys)
t0    = time.time()

for rc, taluka, lat, lon, year in tasks:
    if (rc, year) in done_keys:
        continue

    done += 1
    try:
        feats = extract_all_features(lat, lon, year)
        row = {'taluka': taluka, 'revenue_circle': rc,
               'lat': lat, 'lon': lon, 'year': year,
               'geocode_flag': coords_df.loc[coords_df.revenue_circle == rc, 'geocode_flag'].iloc[0]}
        row.update(feats)
        new_rows.append(row)
        status = '✓'
    except Exception as e:
        new_rows.append({'taluka': taluka, 'revenue_circle': rc,
                         'lat': lat, 'lon': lon, 'year': year,
                         'error': str(e)[:200]})
        status = f'✗ {str(e)[:80]}'

    elapsed  = time.time() - t0
    eta_min  = (elapsed / done) * (total - done) / 60 if done > 0 else 0
    pct      = done / total * 100
    print(f'[{done:03d}/{total}] {pct:.0f}%  {taluka}/{rc} {year}: {status}  '
          f'(elapsed {elapsed/60:.1f}m  ETA {eta_min:.0f}m)', flush=True)

    # Checkpoint every 10 rows
    if done % 10 == 0:
        df_partial = pd.concat([partial_df, pd.DataFrame(new_rows)], ignore_index=True)
        df_partial.to_csv(PARTIAL, index=False)
        print(f'  → checkpoint saved ({len(df_partial)} rows)', flush=True)

# ── Merge new rows with existing v2 ───────────────────────────────────────────
new_df = pd.concat([partial_df, pd.DataFrame(new_rows)], ignore_index=True)
new_df.to_csv(PARTIAL, index=False)
print(f'\n✓ New-year features: {len(new_df)} rows')

# Combine: existing v2 (2021-2025) + new (2018-2020)
# Align columns: v2 has same 21 feature cols, just need to union
all_feats = pd.concat([new_df, existing_v2], ignore_index=True)
all_feats = all_feats.sort_values(['taluka', 'revenue_circle', 'year']).reset_index(drop=True)
all_feats.to_csv(OUT_FEATURES, index=False)
print(f'✓ Full feature set: {len(all_feats)} rows, {len(all_feats.columns)} cols → {OUT_FEATURES}')
print(f'  Years: {sorted(all_feats.year.unique())}')

# ── Join with extended PMFBY (2018-2025) ─────────────────────────────────────
print('\nJoining with PMFBY (2018-2025) monetary loss ratios...')
pmfby = pd.read_csv(PMFBY_FILE)

claim_cols = ['claim_total', 'claim_yield_based', 'claim_localized',
              'claim_prevented_sowing', 'claim_post_harvest',
              'claim_midterm', 'claim_wbcis']
for c in claim_cols + ['sum_insured_rs', 'farmers', 'area_insured_hect']:
    pmfby[c] = pd.to_numeric(pmfby[c], errors='coerce')

pmfby_agg = (pmfby.groupby(['taluka', 'revenue_circle', 'year'])
                   .agg(
                       farmers_total        =('farmers',               'sum'),
                       area_ha              =('area_insured_hect',     'sum'),
                       sum_insured_rs       =('sum_insured_rs',        'sum'),
                       claim_total_lac      =('claim_total',           'sum'),
                       claim_yield_lac      =('claim_yield_based',     'sum'),
                       claim_local_lac      =('claim_localized',       'sum'),
                       claim_prevented_lac  =('claim_prevented_sowing','sum'),
                       claim_postharvest_lac=('claim_post_harvest',    'sum'),
                       claim_midterm_lac    =('claim_midterm',         'sum'),
                   ).reset_index())

denom = pmfby_agg['sum_insured_rs'].replace(0, np.nan)
pmfby_agg['rate_total']       = (pmfby_agg['claim_total_lac']       * 1e5) / denom
pmfby_agg['rate_yield']       = (pmfby_agg['claim_yield_lac']       * 1e5) / denom
pmfby_agg['rate_local']       = (pmfby_agg['claim_local_lac']       * 1e5) / denom
pmfby_agg['rate_prevented']   = (pmfby_agg['claim_prevented_lac']   * 1e5) / denom
pmfby_agg['rate_postharvest'] = (pmfby_agg['claim_postharvest_lac'] * 1e5) / denom
pmfby_agg['rate_midterm']     = (pmfby_agg['claim_midterm_lac']     * 1e5) / denom

all_feats['revenue_circle'] = all_feats['revenue_circle'].str.strip()
pmfby_agg['revenue_circle'] = pmfby_agg['revenue_circle'].str.strip()

model_v3 = all_feats.merge(
    pmfby_agg[['taluka', 'revenue_circle', 'year',
               'farmers_total', 'area_ha', 'sum_insured_rs',
               'claim_total_lac', 'claim_yield_lac', 'claim_local_lac',
               'claim_prevented_lac', 'claim_postharvest_lac', 'claim_midterm_lac',
               'rate_total', 'rate_yield', 'rate_local',
               'rate_prevented', 'rate_postharvest', 'rate_midterm']],
    on=['taluka', 'revenue_circle', 'year'], how='left')

model_v3.to_csv(OUT_MODEL, index=False)

n_match = model_v3['rate_total'].notna().sum()
print(f'✓ Model-ready v3: {len(model_v3)} rows, {n_match} with rate_total')
print(f'  Rows per year:\n{model_v3.groupby("year").size().to_string()}')
print(f'  Saved → {OUT_MODEL}')

print('\n── Rate_total stats (where sum_insured > 0) ──')
for yr in sorted(model_v3.year.unique()):
    vals = model_v3[model_v3.year == yr]['rate_total'].dropna()
    if len(vals) > 0:
        print(f'  {yr}: n={len(vals):3d}  mean={vals.mean():.3f}  max={vals.max():.3f}  '
              f'nonzero={(vals > 0).sum()}')
