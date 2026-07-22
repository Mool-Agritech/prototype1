"""
extract_rc_features.py
──────────────────────
Extracts kharif-season satellite features for all 110 Yavatmal revenue-circle
centroids.  Checkpoints every 10 rows so it can be safely interrupted and resumed.

Usage:
    source .venv/bin/activate
    python3 -u extract_rc_features.py 2>&1 | tee extract_log.txt

Outputs:
    yavatmal_rc_features.csv     (satellite features, one row per RC × year)
    yavatmal_rc_model_ready.csv  (above + PMFBY claim_ratio joined in)
"""

import ee
import pandas as pd
import numpy as np
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
GEE_PROJECT    = 'earth-mrv'
KHARIF_YEARS   = [2021, 2022, 2023, 2024, 2025]
KHARIF_START_MD = '06-01'
KHARIF_END_MD   = '10-31'
BUFFER_M       = 5000    # 5 km radius
SCALE_M        = 1000    # reducer scale
OUT_FEATURES   = Path('yavatmal_rc_features.csv')
OUT_MODEL      = Path('yavatmal_rc_model_ready.csv')

# ── GEE auth ──────────────────────────────────────────────────────────────────
try:
    ee.Initialize(project=GEE_PROJECT)
    print('GEE initialised.')
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)
    print('GEE authenticated + initialised.')

# ── Pre-compute baselines (once, for the whole baseline period 2016-2025) ─────
print('Building baseline images...')
ERA5_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
               .select('temperature_2m_max')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .mean())

NDVI_BASE = (ee.ImageCollection('MODIS/061/MOD13Q1')
               .select('NDVI')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .median().multiply(0.0001))

LST_BASE  = (ee.ImageCollection('MODIS/061/MOD11A2')
               .select('LST_Day_1km')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .mean().multiply(0.02).subtract(273.15))

SM_BASE   = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
               .select('volumetric_soil_water_layer_1')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .mean())

NDVI_MIN  = (ee.ImageCollection('MODIS/061/MOD13Q1')
               .select('NDVI')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .min().multiply(0.0001))
NDVI_MAX  = (ee.ImageCollection('MODIS/061/MOD13Q1')
               .select('NDVI')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .max().multiply(0.0001))
LST_MIN   = (ee.ImageCollection('MODIS/061/MOD11A2')
               .select('LST_Day_1km')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .min().multiply(0.02).subtract(273.15))
LST_MAX   = (ee.ImageCollection('MODIS/061/MOD11A2')
               .select('LST_Day_1km')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .max().multiply(0.02).subtract(273.15))

print('Baseline images ready.')


def extract_features(lat, lon, year):
    pt    = ee.Geometry.Point([lon, lat])
    aoi   = pt.buffer(BUFFER_M)
    start = f'{year}-{KHARIF_START_MD}'
    end   = f'{year}-{KHARIF_END_MD}'

    def red(img, scale=SCALE_M):
        return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)

    # CHIRPS
    chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                .select('precipitation')
                .filter(ee.Filter.date(start, end)))
    cumRain    = red(chirps.sum())
    dry_days   = red(chirps.map(lambda i: i.lt(2).rename('dry')).sum())

    # SPI-30 proxy: standardise cumulative rain against baseline
    chirps_base_mean = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                          .select('precipitation')
                          .filter(ee.Filter.calendarRange(6, 10, 'month'))
                          .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
                          .sum())
    chirps_base_std  = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                          .select('precipitation')
                          .filter(ee.Filter.calendarRange(6, 10, 'month'))
                          .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
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
    tmax_anom = red(era5.mean().subtract(ERA5_BASE))

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
    lst_mean = red(lst_col.mean(), scale=1000)
    lst_anom = lst_col.mean().subtract(LST_BASE).reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # VHI
    ndvi_now = ndvi_col.mean()
    lst_now  = lst_col.mean()
    vci = ndvi_now.subtract(NDVI_MIN).divide(NDVI_MAX.subtract(NDVI_MIN).add(1e-6))
    tci = LST_MAX.subtract(lst_now).divide(LST_MAX.subtract(LST_MIN).add(1e-6))
    vhi = vci.multiply(0.5).add(tci.multiply(0.5)).rename('VHI')
    vhi_val = vhi.reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    result = ee.Dictionary({
        'cumRain_mm':   cumRain.get('precipitation'),
        'SPI30_mean':   spi_val.get('SPI30'),
        'drySpellDays': dry_days.get('dry'),
        'tmax_K_mean':  tmax_mean.get('temperature_2m_max'),
        'tmax_anom_K':  tmax_anom.get('temperature_2m_max'),
        'SM_mean':      sm_mean.get('volumetric_soil_water_layer_1'),
        'SM_anom':      sm_anom.get('volumetric_soil_water_layer_1'),
        'NDVI_peak':    ndvi_peak.get('NDVI'),
        'NDVI_mean':    ndvi_mean.get('NDVI'),
        'NDVI_anom':    ndvi_anom.get('NDVI'),
        'LST_mean_C':   lst_mean.get('LST_Day_1km'),
        'LST_anom_C':   lst_anom.get('LST_Day_1km'),
        'VHI_mean':     vhi_val.get('VHI'),
    })
    return result.getInfo()


# ── Main loop ─────────────────────────────────────────────────────────────────
coords_df = pd.read_csv('yavatmal_rc_coords.csv').dropna(subset=['lat', 'lon'])

if OUT_FEATURES.exists():
    existing = pd.read_csv(OUT_FEATURES)
    done_keys = set(zip(existing['revenue_circle'], existing['year']))
    print(f'Resuming from checkpoint — {len(existing)} rows already done.')
else:
    existing = pd.DataFrame()
    done_keys = set()

rows  = []
total = len(coords_df) * len(KHARIF_YEARS)
done  = len(done_keys)
t0    = time.time()

for _, site in coords_df.iterrows():
    rc     = site['revenue_circle']
    taluka = site['taluka']
    lat    = site['lat']
    lon    = site['lon']

    for year in KHARIF_YEARS:
        if (rc, year) in done_keys:
            continue

        done += 1
        try:
            feats = extract_features(lat, lon, year)
            row = {'taluka': taluka, 'revenue_circle': rc,
                   'lat': lat, 'lon': lon, 'year': year,
                   'geocode_flag': site['geocode_flag']}
            row.update(feats)
            rows.append(row)
            status = '✓'
        except Exception as e:
            rows.append({'taluka': taluka, 'revenue_circle': rc,
                         'lat': lat, 'lon': lon, 'year': year,
                         'geocode_flag': site['geocode_flag'],
                         'error': str(e)[:200]})
            status = f'✗ {str(e)[:80]}'

        elapsed = time.time() - t0
        eta_min = (elapsed / done) * (total - done) / 60 if done > 0 else 0
        print(f'[{done:03d}/{total}] {done/total*100:.0f}% — '
              f'{taluka}/{rc} {year}: {status}  '
              f'(elapsed {elapsed/60:.1f}m, ETA {eta_min:.0f}m)', flush=True)

        # Checkpoint every 10 rows
        if done % 10 == 0:
            df_partial = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
            df_partial.to_csv(OUT_FEATURES, index=False)

# Final features save
df_feats = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
df_feats.to_csv(OUT_FEATURES, index=False)
print(f'\n✓ Features saved: {len(df_feats)} rows → {OUT_FEATURES}')

# ── Join with PMFBY ───────────────────────────────────────────────────────────
print('\nJoining with PMFBY claim data...')
pmfby = pd.read_csv('pmfby_yavatmal_iu_kharif.csv')
for c in ['farmers', 'claim_total', 'sum_insured_rs']:
    pmfby[c] = pd.to_numeric(pmfby[c], errors='coerce')

pmfby_rc = (pmfby.groupby(['taluka', 'revenue_circle', 'year'])
                 .agg(farmers_total=('farmers', 'sum'),
                      claim_farmers=('claim_total', 'sum'),
                      sum_insured=('sum_insured_rs', 'sum'))
                 .reset_index())
pmfby_rc['claim_ratio'] = (pmfby_rc['claim_farmers']
                            / pmfby_rc['farmers_total'].replace(0, np.nan))

df_feats['revenue_circle'] = df_feats['revenue_circle'].str.strip()
pmfby_rc['revenue_circle'] = pmfby_rc['revenue_circle'].str.strip()

merged = df_feats.merge(
    pmfby_rc[['taluka', 'revenue_circle', 'year',
              'claim_ratio', 'farmers_total', 'claim_farmers', 'sum_insured']],
    on=['taluka', 'revenue_circle', 'year'], how='left')
merged.to_csv(OUT_MODEL, index=False)

n_match = merged['claim_ratio'].notna().sum()
print(f'✓ Model-ready dataset: {len(merged)} rows, {n_match} with claim_ratio')
print(f'  Saved → {OUT_MODEL}')
