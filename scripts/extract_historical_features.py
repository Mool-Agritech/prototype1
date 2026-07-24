"""
extract_historical_features.py
────────────────────────────────
Extracts Kharif satellite features for 2003-2017 for all 277 RCs × 4 districts.
Extends our dataset from 8 years → 23 years for better APY yield calibration.

Features extracted (per RC-year):
  ── Always available (2003+) ──
  • CHIRPS rainfall (daily 5km): cumRain, june_rain, oct_rain, heavy_rain_days,
                                  drySpellDays, dry_spell_julaug, sub-window rain
  • MODIS NDVI (MOD13A2 16-day 250m): NDVI_mean, NDVI_anom, NDVI_peak, sub-window NDVI
  • MODIS LST (MOD11A2 8-day 1km): LST_mean_C, LST_anom_C, lst_anom_augsep
  • MODIS VHI (derived): VHI_mean
  • MODIS FAPAR (MCD15A3H 4-day 500m): FAPAR_mean, FAPAR_anom  [from 2002]
  • ERA5 temperature: tmax_mean_C, tmax_anom_C, gdd_surplus
  • ERA5 soil moisture: SM_mean, SM_anom, sm_wet_days

  ── Partial (2015+) — null for earlier years ──
  • NASA SMAP (SPL3SMP_E 9km): SMAP_sm_mean, SMAP_sm_anom
  • Sentinel-1 SAR (IW 10m): SAR_VH_mean_dB, SAR_CR_mean_dB, sub-window SAR VH

Coverage: 277 RCs × 15 years (2003-2017) = 4,155 RC-years

Usage:
    source .venv/bin/activate
    python3 -u scripts/extract_historical_features.py 2>&1 | tee logs/extract_historical.log
"""

import ee
import pandas as pd
import numpy as np
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
GEE_PROJECT  = 'earth-mrv'
ALL_YEARS    = list(range(2003, 2018))   # 2003-2017 inclusive
BUFFER_M     = 5000
SCALE_M      = 1000
N_WORKERS    = 20   # double the previous scripts

KHARIF_START = '06-01'
KHARIF_END   = '10-31'
BASE_WINDOW  = ('2003-01-01', '2026-01-01')  # long-term baseline for anomalies

YAVATMAL_COORDS = Path('data/processed/yavatmal_rc_coords.csv')
NEW_COORDS      = Path('data/processed/new_districts_rc_coords.csv')
PARTIAL         = Path('data/processed/historical_features_partial.csv')
OUT             = Path('data/processed/historical_features_2003_2017.csv')

# ── GEE auth ──────────────────────────────────────────────────────────────────
try:
    ee.Initialize(project=GEE_PROJECT)
    print('GEE initialised.', flush=True)
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)
    print('GEE authenticated + initialised.', flush=True)

# ── Baselines (built once, reused across all threads) ─────────────────────────
print('Building baseline images... (long-term 2003-2026)', flush=True)

NDVI_BASE = (ee.ImageCollection('MODIS/061/MOD13A2')
               .select('NDVI')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date(*BASE_WINDOW))
               .mean().multiply(0.0001))

NDVI_MIN = (ee.ImageCollection('MODIS/061/MOD13A2')
              .select('NDVI')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .min().multiply(0.0001))

NDVI_MAX = (ee.ImageCollection('MODIS/061/MOD13A2')
              .select('NDVI')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .max().multiply(0.0001))

LST_BASE = (ee.ImageCollection('MODIS/061/MOD11A2')
              .select('LST_Day_1km')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .mean().multiply(0.02).subtract(273.15))

LST_MIN = (ee.ImageCollection('MODIS/061/MOD11A2')
             .select('LST_Day_1km')
             .filter(ee.Filter.calendarRange(6, 10, 'month'))
             .filter(ee.Filter.date(*BASE_WINDOW))
             .min().multiply(0.02).subtract(273.15))

LST_MAX = (ee.ImageCollection('MODIS/061/MOD11A2')
             .select('LST_Day_1km')
             .filter(ee.Filter.calendarRange(6, 10, 'month'))
             .filter(ee.Filter.date(*BASE_WINDOW))
             .max().multiply(0.02).subtract(273.15))

LST_BASE_AUGSEP = (ee.ImageCollection('MODIS/061/MOD11A2')
                     .select('LST_Day_1km')
                     .filter(ee.Filter.calendarRange(8, 9, 'month'))
                     .filter(ee.Filter.date(*BASE_WINDOW))
                     .mean().multiply(0.02).subtract(273.15))

SM_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
             .select('volumetric_soil_water_layer_1')
             .filter(ee.Filter.calendarRange(6, 10, 'month'))
             .filter(ee.Filter.date(*BASE_WINDOW))
             .mean())

ERA5_TMAX_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                    .select('temperature_2m_max')
                    .filter(ee.Filter.calendarRange(6, 10, 'month'))
                    .filter(ee.Filter.date(*BASE_WINDOW))
                    .mean())

GDD_BASE = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
              .select('temperature_2m_max')
              .filter(ee.Filter.calendarRange(6, 10, 'month'))
              .filter(ee.Filter.date(*BASE_WINDOW))
              .map(lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat'))
              .mean())

FAPAR_BASE = (ee.ImageCollection('MODIS/061/MCD15A3H')
                .select('Fpar')
                .filter(ee.Filter.calendarRange(6, 10, 'month'))
                .filter(ee.Filter.date(*BASE_WINDOW))
                .mean().multiply(0.01))

SMAP_BASE = (ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006')
               .select('soil_moisture_am')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2015-04-01', '2026-01-01'))
               .mean())

print('Baselines ready.', flush=True)

SUB_WINDOWS = {
    'junjul': ('06-01', '07-31'),
    'augsep': ('08-01', '09-30'),
    'oct':    ('10-01', '10-31'),
}


def safe_get(d, key):
    return ee.Algorithms.If(d.contains(key), d.get(key), None)


def red(img, aoi, scale=SCALE_M):
    return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)


def extract_historical(lat, lon, year):
    """Extract all features in one batched GEE call per RC-year."""
    pt    = ee.Geometry.Point([lon, lat])
    aoi   = pt.buffer(BUFFER_M)
    start = f'{year}-{KHARIF_START}'
    end   = f'{year}-{KHARIF_END}'

    null_img = ee.Image(0).updateMask(ee.Image(0))

    # ── CHIRPS Rainfall ────────────────────────────────────────────────────────
    chirps = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                .select('precipitation')
                .filter(ee.Filter.date(start, end)))
    cum_rain   = red(chirps.sum(), aoi)
    dry_days   = red(chirps.map(lambda i: i.lt(2).rename('dry')).sum(), aoi)

    june_rain  = red((ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                        .select('precipitation')
                        .filter(ee.Filter.date(f'{year}-06-01', f'{year}-06-16'))).sum(), aoi)
    oct_rain   = red((ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                        .select('precipitation')
                        .filter(ee.Filter.date(f'{year}-10-01', f'{year}-11-01'))).sum(), aoi)
    heavy_days = red((ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                        .select('precipitation')
                        .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
                     .map(lambda i: i.gt(50).rename('heavy')).sum(), aoi)
    dry_julaug = red((ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                        .select('precipitation')
                        .filter(ee.Filter.date(f'{year}-07-20', f'{year}-09-01')))
                     .map(lambda i: i.lt(2).rename('dry')).sum(), aoi)

    # ── MODIS NDVI ────────────────────────────────────────────────────────────
    ndvi_col = (ee.ImageCollection('MODIS/061/MOD13A2')
                  .select('NDVI')
                  .filter(ee.Filter.date(start, end))
                  .map(lambda i: i.multiply(0.0001)))
    ndvi_mean_r = ndvi_col.mean().reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)
    ndvi_anom_r = ndvi_col.mean().subtract(NDVI_BASE).reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)
    ndvi_peak_r = ndvi_col.max().reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)

    # ── MODIS LST ─────────────────────────────────────────────────────────────
    lst_col = (ee.ImageCollection('MODIS/061/MOD11A2')
                 .select('LST_Day_1km')
                 .filter(ee.Filter.date(start, end))
                 .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_mean_r = lst_col.mean().reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)
    lst_anom_r = lst_col.mean().subtract(LST_BASE).reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)
    lst_augsep_col = (ee.ImageCollection('MODIS/061/MOD11A2')
                        .select('LST_Day_1km')
                        .filter(ee.Filter.date(f'{year}-08-01', f'{year}-10-01'))
                        .map(lambda i: i.multiply(0.02).subtract(273.15)))
    lst_augsep_r = lst_augsep_col.mean().subtract(LST_BASE_AUGSEP).reduceRegion(
        ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # ── VHI ───────────────────────────────────────────────────────────────────
    ndvi_now = ndvi_col.mean()
    lst_now  = lst_col.mean()
    vci = ndvi_now.subtract(NDVI_MIN).divide(NDVI_MAX.subtract(NDVI_MIN).add(1e-6))
    tci = LST_MAX.subtract(lst_now).divide(LST_MAX.subtract(LST_MIN).add(1e-6))
    vhi = vci.multiply(0.5).add(tci.multiply(0.5)).rename('VHI')
    vhi_r = vhi.reduceRegion(ee.Reducer.mean(), aoi, 1000, maxPixels=1e7)

    # ── NDVI slow greenup ─────────────────────────────────────────────────────
    ndvi_junjul = (ee.ImageCollection('MODIS/061/MOD13A2')
                     .select('NDVI')
                     .filter(ee.Filter.date(f'{year}-06-01', f'{year}-08-01'))
                     .map(lambda i: i.multiply(0.0001)))
    slow_greenup_r = ndvi_junjul.map(lambda i: i.lt(0.3).rename('slow')).sum().reduceRegion(
        ee.Reducer.mean(), aoi, 500, maxPixels=1e7)

    # ── ERA5 Temperature ──────────────────────────────────────────────────────
    era5_t = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                .select('temperature_2m_max')
                .filter(ee.Filter.date(start, end)))
    tmax_mean_r = red(era5_t.mean().subtract(273.15).rename('tmax'), aoi)
    tmax_anom_r = red(era5_t.mean().subtract(ERA5_TMAX_BASE).rename('tmax'), aoi)
    gdd_r = red(era5_t.map(lambda i: i.subtract(308.15).max(ee.Image(0)).rename('heat'))
                .mean().subtract(GDD_BASE).rename('gdd'), aoi)

    # ── ERA5 Soil Moisture ────────────────────────────────────────────────────
    sm_col = (ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                .select('volumetric_soil_water_layer_1')
                .filter(ee.Filter.date(start, end)))
    sm_mean_r = red(sm_col.mean(), aoi)
    sm_anom_r = red(sm_col.mean().subtract(SM_BASE), aoi)
    sm_wet_r  = red((ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR')
                       .select('volumetric_soil_water_layer_1')
                       .filter(ee.Filter.date(f'{year}-06-01', f'{year}-11-01')))
                    .map(lambda i: i.gt(SM_BASE).rename('wet')).sum(), aoi)

    # ── MODIS FAPAR ───────────────────────────────────────────────────────────
    fapar_col = (ee.ImageCollection('MODIS/061/MCD15A3H')
                   .select('Fpar')
                   .filter(ee.Filter.date(start, end))
                   .map(lambda i: i.multiply(0.01)))
    has_fapar = fapar_col.size().gt(0)
    fapar_null = FAPAR_BASE.updateMask(ee.Image(0))
    fapar_mean_img = ee.Image(ee.Algorithms.If(has_fapar, fapar_col.mean(), fapar_null))
    fapar_anom_img = ee.Image(ee.Algorithms.If(has_fapar,
                              fapar_col.mean().subtract(FAPAR_BASE), fapar_null))
    fapar_mean_r = safe_get(red(fapar_mean_img, aoi), 'Fpar')
    fapar_anom_r = safe_get(red(fapar_anom_img, aoi), 'Fpar')

    # ── SMAP (2015+; null before) ─────────────────────────────────────────────
    smap_col = (ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006')
                  .select('soil_moisture_am')
                  .filter(ee.Filter.date(start, end)))
    has_smap = smap_col.size().gt(0)
    smap_null = SMAP_BASE.updateMask(ee.Image(0))
    smap_mean_img = ee.Image(ee.Algorithms.If(has_smap, smap_col.mean(), smap_null))
    smap_anom_img = ee.Image(ee.Algorithms.If(has_smap,
                              smap_col.mean().subtract(SMAP_BASE), smap_null))
    smap_mean_r = safe_get(red(smap_mean_img, aoi), 'soil_moisture_am')
    smap_anom_r = safe_get(red(smap_anom_img, aoi), 'soil_moisture_am')

    # ── Sentinel-1 SAR (2015+; null before) ──────────────────────────────────
    s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            .filter(ee.Filter.date(start, end))
            .select(['VV', 'VH']))
    has_s1  = s1.size().gt(0)
    vh_null = ee.Image(0).rename('VH').updateMask(ee.Image(0))
    cr_null = ee.Image(0).rename('CR').updateMask(ee.Image(0))
    sar_vh_r  = red(ee.Image(ee.Algorithms.If(has_s1, s1.select('VH').mean(), vh_null)), aoi)
    s1_cr     = s1.map(lambda i: i.select('VH').subtract(i.select('VV')).rename('CR'))
    sar_cr_r  = red(ee.Image(ee.Algorithms.If(has_s1, s1_cr.mean(), cr_null)), aoi)

    # ── Sub-window features ───────────────────────────────────────────────────
    sw_results = {}
    for wname, (w_start_md, w_end_md) in SUB_WINDOWS.items():
        w_start = f'{year}-{w_start_md}'
        w_end   = f'{year}-{w_end_md}'

        # NDVI sub-window
        sw_ndvi = (ee.ImageCollection('MODIS/061/MOD13A2')
                     .select('NDVI')
                     .filter(ee.Filter.date(w_start, w_end))
                     .map(lambda i: i.multiply(0.0001)))
        has_n = sw_ndvi.size().gt(0)
        n_img = ee.Image(ee.Algorithms.If(has_n, sw_ndvi.mean(),
                         NDVI_BASE.updateMask(ee.Image(0))))
        nr = n_img.reduceRegion(ee.Reducer.mean(), aoi, 500, maxPixels=1e7)
        sw_results[f'NDVI_{wname}'] = safe_get(nr, 'NDVI')

        # Rainfall sub-window
        sw_rain = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .select('precipitation')
                     .filter(ee.Filter.date(w_start, w_end)))
        has_r = sw_rain.size().gt(0)
        r_img = ee.Image(ee.Algorithms.If(has_r, sw_rain.sum(),
                         ee.Image(0).rename('precipitation').updateMask(ee.Image(0))))
        rr = red(r_img, aoi)
        sw_results[f'rain_{wname}_mm'] = safe_get(rr, 'precipitation')

        # SMAP sub-window (2015+ only)
        sw_smap = (ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006')
                     .select('soil_moisture_am')
                     .filter(ee.Filter.date(w_start, w_end)))
        has_ss = sw_smap.size().gt(0)
        ss_img = ee.Image(ee.Algorithms.If(has_ss, sw_smap.mean(),
                          ee.Image(0).rename('soil_moisture_am').updateMask(ee.Image(0))))
        sr = red(ss_img, aoi)
        sw_results[f'SM_{wname}'] = safe_get(sr, 'soil_moisture_am')

        # SAR VH sub-window (2015+ only)
        sw_sar = (ee.ImageCollection('COPERNICUS/S1_GRD')
                    .filter(ee.Filter.eq('instrumentMode', 'IW'))
                    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
                    .filter(ee.Filter.date(w_start, w_end))
                    .select('VH'))
        has_v = sw_sar.size().gt(0)
        v_img = ee.Image(ee.Algorithms.If(has_v, sw_sar.mean(),
                         ee.Image(0).rename('VH').updateMask(ee.Image(0))))
        vr = red(v_img, aoi)
        sw_results[f'SAR_VH_{wname}_dB'] = safe_get(vr, 'VH')

    result = ee.Dictionary({
        # CHIRPS
        'cumRain_mm':         safe_get(cum_rain, 'precipitation'),
        'drySpellDays':       safe_get(dry_days, 'dry'),
        'june_rain_mm':       safe_get(june_rain, 'precipitation'),
        'oct_rain_mm':        safe_get(oct_rain, 'precipitation'),
        'heavy_rain_days':    safe_get(heavy_days, 'heavy'),
        'dry_spell_julaug':   safe_get(dry_julaug, 'dry'),
        # NDVI
        'NDVI_mean':          safe_get(ndvi_mean_r, 'NDVI'),
        'NDVI_anom':          safe_get(ndvi_anom_r, 'NDVI'),
        'NDVI_peak':          safe_get(ndvi_peak_r, 'NDVI'),
        'ndvi_slow_greenup':  safe_get(slow_greenup_r, 'slow'),
        # LST
        'LST_mean_C':         safe_get(lst_mean_r, 'LST_Day_1km'),
        'LST_anom_C':         safe_get(lst_anom_r, 'LST_Day_1km'),
        'lst_anom_augsep':    safe_get(lst_augsep_r, 'LST_Day_1km'),
        # VHI
        'VHI_mean':           safe_get(vhi_r, 'VHI'),
        # ERA5 temperature
        'tmax_mean_C':        safe_get(tmax_mean_r, 'tmax'),
        'tmax_anom_C':        safe_get(tmax_anom_r, 'tmax'),
        'gdd_surplus':        safe_get(gdd_r, 'gdd'),
        # ERA5 soil moisture
        'SM_mean':            safe_get(sm_mean_r, 'volumetric_soil_water_layer_1'),
        'SM_anom':            safe_get(sm_anom_r, 'volumetric_soil_water_layer_1'),
        'sm_wet_days':        safe_get(sm_wet_r, 'wet'),
        # FAPAR
        'FAPAR_mean':         fapar_mean_r,
        'FAPAR_anom':         fapar_anom_r,
        # SMAP (null pre-2015)
        'SMAP_sm_mean':       smap_mean_r,
        'SMAP_sm_anom':       smap_anom_r,
        # SAR (null pre-2015)
        'SAR_VH_mean_dB':     safe_get(sar_vh_r, 'VH'),
        'SAR_CR_mean_dB':     safe_get(sar_cr_r, 'CR'),
        **sw_results,
    })
    return result.getInfo()


def process_one(item):
    dist, tal, rc, lat, lon, yr = item
    for attempt in range(4):
        try:
            feats = extract_historical(lat, lon, yr)
            feats.update({'district': dist, 'taluka': tal, 'revenue_circle': rc,
                          'lat': lat, 'lon': lon, 'year': yr})
            return feats
        except Exception as e:
            wait = 8 * (attempt + 1)
            print(f'  RETRY {attempt+1}/4 {rc}/{yr}: {str(e)[:60]} (wait {wait}s)', flush=True)
            time.sleep(wait)
    # all retries failed
    print(f'  FAILED {rc}/{yr} after 4 attempts', flush=True)
    return {'district': dist, 'taluka': tal, 'revenue_circle': rc,
            'lat': lat, 'lon': lon, 'year': yr}


# ── Load all RC coords ────────────────────────────────────────────────────────
yav = pd.read_csv(YAVATMAL_COORDS).dropna(subset=['lat', 'lon'])
yav['district'] = 'Yavatmal'
new = pd.read_csv(NEW_COORDS).dropna(subset=['lat', 'lon'])
all_coords = pd.concat([yav, new], ignore_index=True)
print(f"Total RCs: {len(all_coords)} | Years: {ALL_YEARS[0]}-{ALL_YEARS[-1]} "
      f"| Total RC-years: {len(all_coords) * len(ALL_YEARS)}", flush=True)
print(f"Workers: {N_WORKERS}", flush=True)

# ── Checkpoint (resume support) ───────────────────────────────────────────────
done_keys = set()
partial_rows = []
if PARTIAL.exists():
    pdf = pd.read_csv(PARTIAL)
    for _, r in pdf.iterrows():
        done_keys.add((r['district'], r['taluka'], r['revenue_circle'], int(r['year'])))
        partial_rows.append(r.to_dict())
    print(f"Checkpoint: {len(done_keys)} already done.", flush=True)

# ── Build work list ───────────────────────────────────────────────────────────
work = []
for _, row in all_coords.iterrows():
    for yr in ALL_YEARS:
        key = (row['district'], row['taluka'], row['revenue_circle'], yr)
        if key not in done_keys:
            work.append((row['district'], row['taluka'], row['revenue_circle'],
                         float(row['lat']), float(row['lon']), yr))

total = len(all_coords) * len(ALL_YEARS)
print(f"Remaining: {len(work)}/{total} RC-years to extract.", flush=True)

if not work:
    print("Nothing to do. Saving final output.", flush=True)
else:
    lock = threading.Lock()
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
        futures = {executor.submit(process_one, item): item for item in work}
        for future in as_completed(futures):
            result = future.result()
            with lock:
                partial_rows.append(result)
                completed += 1
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 1
                eta_min = (len(work) - completed) / rate / 60
                pct = (len(done_keys) + completed) / total * 100
                yr = result.get('year', '?')
                dist = result.get('district', '?')
                rc = result.get('revenue_circle', '?')
                ndvi = result.get('NDVI_mean') or 0
                rain = result.get('cumRain_mm') or 0
                fapar = result.get('FAPAR_mean') or 0
                smap = result.get('SMAP_sm_mean') or 0
                print(f"[{len(done_keys)+completed:>5d}/{total}] "
                      f"{dist}/{rc}/{yr}  "
                      f"NDVI={ndvi:.3f} Rain={rain:.0f}mm FAPAR={fapar:.3f} SMAP={smap:.3f}  "
                      f"({pct:.1f}%  ETA {eta_min:.0f}m)", flush=True)

                if completed % 100 == 0:
                    df_tmp = pd.DataFrame(partial_rows)
                    df_tmp.to_csv(PARTIAL, index=False)
                    print(f"  ── checkpoint saved ({len(partial_rows)} rows) ──", flush=True)

# ── Final save ────────────────────────────────────────────────────────────────
final = pd.DataFrame(partial_rows)
final.to_csv(OUT, index=False)
print(f"\n✓ Done: {len(final)} rows → {OUT}", flush=True)
print(f"  Years: {sorted(final['year'].unique())}", flush=True)
print(f"  Null counts per feature:", flush=True)
for c in sorted(final.columns):
    if c not in ['district','taluka','revenue_circle','lat','lon','year']:
        n = final[c].isna().sum()
        if n > 0:
            print(f"    {c}: {n} null ({n/len(final)*100:.1f}%)", flush=True)
print("\nRun merge_historical.py next to combine with 2018-2025 data.", flush=True)
