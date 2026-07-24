"""
extract_new_districts_features.py
───────────────────────────────────
Extract all 21 GEE features for Amravati, Wardha, and Chandrapur
revenue circle centroids, for Kharif years 2018–2025.

Outputs:
    data/processed/new_districts_rc_features.csv     — all RC×year rows
    data/processed/new_districts_model_ready.csv     — joined with PMFBY data

Usage:
    source .venv/bin/activate
    python3 -u scripts/extract_new_districts_features.py 2>&1 | tee logs/extract_new_districts.log
"""

import ee
import pandas as pd
import numpy as np
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
GEE_PROJECT  = 'earth-mrv'
ALL_YEARS    = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
BUFFER_M     = 5000
SCALE_M      = 1000
KHARIF_START = '06-01'
KHARIF_END   = '10-31'

COORDS_FILE  = Path('data/processed/new_districts_rc_coords.csv')
PARTIAL      = Path('data/processed/new_districts_rc_features_partial.csv')
OUT_FEATURES = Path('data/processed/new_districts_rc_features.csv')
OUT_MODEL    = Path('data/processed/new_districts_model_ready.csv')

PMFBY_FILES = {
    'Amravati':   Path('data/raw/pmfby_amravati_iu_kharif.csv'),
    'Wardha':     Path('data/raw/pmfby_wardha_iu_kharif.csv'),
    'Chandrapur': Path('data/raw/pmfby_chandrapur_iu_kharif.csv'),
}

# ── GEE auth ──────────────────────────────────────────────────────────────────
try:
    ee.Initialize(project=GEE_PROJECT)
    print('GEE initialised.')
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)
    print('GEE authenticated + initialised.')

# ── Baselines (same window as yavatmal v3) ────────────────────────────────────
BASE_WINDOW = ('2016-01-01', '2026-01-01')
print('Building baselines...', flush=True)

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

print('Baselines ready.', flush=True)


def extract_all_features(lat, lon, year):
    """Extract all 21 features for a single RC-year."""
    pt    = ee.Geometry.Point([lon, lat])
    aoi   = pt.buffer(BUFFER_M)
    start = f'{year}-{KHARIF_START}'
    end   = f'{year}-{KHARIF_END}'

    def red(img, scale=SCALE_M):
        return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)

    # ── V1 FEATURES ───────────────────────────────────────────────────────────
    chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                .select('precipitation')
                .filter(ee.Filter.date(start, end)))
    cumRain  = red(chirps.sum())
    dry_days = red(chirps.map(lambda i: i.lt(2).rename('dry')).sum())

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

    era5 = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
              .select('temperature_2m_max')
              .filter(ee.Filter.date(start, end)))
    tmax_mean = red(era5.mean())
    tmax_anom = red(era5.mean().subtract(ERA5_TMAX_BASE))

    sm = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
            .select('volumetric_soil_water_layer_1')
            .filter(ee.Filter.date(start, end)))
    sm_mean = red(sm.mean())
    sm_anom = red(sm.mean().subtract(SM_BASE))

    ndvi = (ee.ImageCollection('MODIS/061/MOD13Q1')
              .select('NDVI')
              .filter(ee.Filter.date(start, end))
              .map(lambda i: i.multiply(0.0001)))
    ndvi_mean = red(ndvi.mean())
    ndvi_anom = red(ndvi.mean().subtract(NDVI_BASE))

    lst = (ee.ImageCollection('MODIS/061/MOD11A2')
             .select('LST_Day_1km')
             .filter(ee.Filter.date(start, end))
             .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_mean = red(lst.mean())
    lst_anom = red(lst.mean().subtract(LST_BASE))

    vhi_img = (ndvi.mean().subtract(NDVI_MIN)
               .divide(NDVI_MAX.subtract(NDVI_MIN).add(1e-6))
               .multiply(0.5)
               .add(lst.mean().subtract(LST_MIN)
                    .divide(LST_MAX.subtract(LST_MIN).add(1e-6))
                    .multiply(0.5))
               .rename('VHI'))
    vhi_mean = red(vhi_img)

    s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .filter(ee.Filter.date(start, end))
            .select('VV'))
    sar_mean = red(s1.mean())

    # ── V2 FEATURES ───────────────────────────────────────────────────────────
    june_chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .select('precipitation')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-06-30')))
    june_rain = red(june_chirps.sum())

    oct_chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                    .select('precipitation')
                    .filter(ee.Filter.date(f'{year}-10-01', f'{year}-10-31')))
    oct_rain = red(oct_chirps.sum())

    heavy_days = red(chirps.map(lambda i: i.gt(50).rename('heavy')).sum())

    julaug_chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                       .select('precipitation')
                       .filter(ee.Filter.date(f'{year}-07-01', f'{year}-08-31')))
    dry_julaug = red(julaug_chirps.map(lambda i: i.lt(2).rename('dry')).sum())

    lst_augsep = (ee.ImageCollection('MODIS/061/MOD11A2')
                    .select('LST_Day_1km')
                    .filter(ee.Filter.date(f'{year}-08-01', f'{year}-09-30'))
                    .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_anom_augsep = red(lst_augsep.mean().subtract(LST_BASE_AUGSEP))

    sm_wet_days = red(sm.map(lambda i: i.gt(SM_BASE).rename('wet')).sum())

    gdd = (era5.map(lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat')))
    gdd_anom = red(gdd.mean().subtract(GDD_BASE_DAILY_MEAN))

    # NDVI slow greenup: NDVI in June vs mean baseline
    ndvi_june = (ee.ImageCollection('MODIS/061/MOD13Q1')
                   .select('NDVI')
                   .filter(ee.Filter.date(f'{year}-06-01', f'{year}-06-30'))
                   .map(lambda i: i.multiply(0.0001)))
    ndvi_june_mean = red(ndvi_june.mean())
    ndvi_base_june = (ee.ImageCollection('MODIS/061/MOD13Q1')
                        .select('NDVI')
                        .filter(ee.Filter.calendarRange(6, 6, 'month'))
                        .filter(ee.Filter.date(*BASE_WINDOW))
                        .median().multiply(0.0001))
    ndvi_slow = red(ndvi_june.mean().subtract(ndvi_base_june))

    # ── Combine ───────────────────────────────────────────────────────────────
    result = ee.Dictionary({
        'cumRain_mm':       cumRain.get('precipitation'),
        'drySpellDays':     dry_days.get('dry'),
        'SPI30_min':        spi_val.get('SPI30'),
        'tmax_mean_C':      tmax_mean.get('temperature_2m_max'),
        'tmax_anom_C':      tmax_anom.get('temperature_2m_max'),
        'sm_mean':          sm_mean.get('volumetric_soil_water_layer_1'),
        'sm_anom':          sm_anom.get('volumetric_soil_water_layer_1'),
        'NDVI_mean':        ndvi_mean.get('NDVI'),
        'NDVI_anom':        ndvi_anom.get('NDVI'),
        'LST_mean_C':       lst_mean.get('LST_Day_1km'),
        'LST_anom_C':       lst_anom.get('LST_Day_1km'),
        'VHI_mean':         vhi_mean.get('VHI'),
        'SAR_VV_mean_dB':   sar_mean.get('VV'),
        'june_rain_mm':     june_rain.get('precipitation'),
        'oct_rain_mm':      oct_rain.get('precipitation'),
        'heavy_rain_days':  heavy_days.get('heavy'),
        'dry_spell_julaug': dry_julaug.get('dry'),
        'lst_anom_augsep':  lst_anom_augsep.get('LST_Day_1km'),
        'sm_wet_days':      sm_wet_days.get('wet'),
        'gdd_surplus':      gdd_anom.get('heat'),
        'ndvi_slow_greenup': ndvi_slow.get('NDVI'),
    })
    return result.getInfo()


# ── Load coords ───────────────────────────────────────────────────────────────
coords_df = pd.read_csv(COORDS_FILE)
coords_df = coords_df.dropna(subset=['lat', 'lon'])
print(f"Loaded {len(coords_df)} RC centroids across 3 districts.", flush=True)

# ── Load checkpoint ───────────────────────────────────────────────────────────
done_keys = set()
partial_rows = []
if PARTIAL.exists():
    partial_df = pd.read_csv(PARTIAL)
    for _, r in partial_df.iterrows():
        key = (r['district'], r['taluka'], r['revenue_circle'], int(r['year']))
        done_keys.add(key)
        partial_rows.append(r.to_dict())
    print(f"Checkpoint: {len(done_keys)} RC-years already done.", flush=True)

# ── Build work list ───────────────────────────────────────────────────────────
work = []
for _, row in coords_df.iterrows():
    for yr in ALL_YEARS:
        key = (row['district'], row['taluka'], row['revenue_circle'], yr)
        if key not in done_keys:
            work.append((row['district'], row['taluka'], row['revenue_circle'],
                         float(row['lat']), float(row['lon']), yr))

total_work = len(coords_df) * len(ALL_YEARS)
print(f"Remaining: {len(work)}/{total_work} RC-years to extract.", flush=True)

# ── Main extraction loop ──────────────────────────────────────────────────────
CKPT_EVERY = 10
new_rows = []

for i, (dist, tal, rc, lat, lon, yr) in enumerate(work):
    for attempt in range(3):
        try:
            feats = extract_all_features(lat, lon, yr)
            feats.update({'district': dist, 'taluka': tal, 'revenue_circle': rc,
                          'lat': lat, 'lon': lon, 'year': yr})
            new_rows.append(feats)
            partial_rows.append(feats)

            done_pct = (len(done_keys) + i + 1) / total_work * 100
            print(f"[{i+1}/{len(work)}] {dist}/{rc}/{yr}: "
                  f"rain={feats.get('cumRain_mm',0):.0f}mm "
                  f"VHI={feats.get('VHI_mean',0):.3f} "
                  f"({done_pct:.1f}%)", flush=True)
            break
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}", flush=True)
            time.sleep(5 * (attempt + 1))

    # Checkpoint
    if (i + 1) % CKPT_EVERY == 0:
        pd.DataFrame(partial_rows).to_csv(PARTIAL, index=False)
        print(f"  ── checkpoint saved ({len(partial_rows)} rows) ──", flush=True)

# ── Final save ────────────────────────────────────────────────────────────────
all_df = pd.DataFrame(partial_rows)
all_df.to_csv(OUT_FEATURES, index=False)
print(f"\n✓ Features saved: {len(all_df)} rows → {OUT_FEATURES}", flush=True)

# ── Merge with PMFBY ──────────────────────────────────────────────────────────
pmfby_frames = []
for dist, fpath in PMFBY_FILES.items():
    df = pd.read_csv(fpath)
    df['district'] = dist
    pmfby_frames.append(df)
pmfby = pd.concat(pmfby_frames, ignore_index=True)

# Normalize types
for col in ['year', 'claim_total', 'claim_yield_based', 'claim_localized', 'sum_insured_rs']:
    pmfby[col] = pd.to_numeric(pmfby[col], errors='coerce').fillna(0)

# Aggregate to (district, taluka, revenue_circle, year)
pmfby_agg = (pmfby.groupby(['district', 'taluka', 'revenue_circle', 'year'], as_index=False)
             .agg(claim_total_lac=('claim_total', 'sum'),
                  claim_yield_lac=('claim_yield_based', 'sum'),
                  claim_local_lac=('claim_localized', 'sum'),
                  sum_insured_rs=('sum_insured_rs', 'sum')))

pmfby_agg['rate_total'] = (pmfby_agg['claim_total_lac'] * 1e5) / pmfby_agg['sum_insured_rs'].replace(0, np.nan)
pmfby_agg['rate_yield'] = (pmfby_agg['claim_yield_lac'] * 1e5) / pmfby_agg['sum_insured_rs'].replace(0, np.nan)
pmfby_agg['rate_local'] = (pmfby_agg['claim_local_lac'] * 1e5) / pmfby_agg['sum_insured_rs'].replace(0, np.nan)

# Merge
model_df = all_df.merge(pmfby_agg,
                        on=['district', 'taluka', 'revenue_circle', 'year'],
                        how='left')
model_df.to_csv(OUT_MODEL, index=False)
print(f"✓ Model-ready saved: {len(model_df)} rows → {OUT_MODEL}", flush=True)
print(f"  Rows with PMFBY data: {model_df['rate_total'].notna().sum()}", flush=True)
