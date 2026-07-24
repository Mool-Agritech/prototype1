"""
extract_chf_features.py
───────────────────────
Extracts features for CHF (Crop Health Factor) composite index:

  1. FAPAR — MODIS MCD15A3H 4-day 500m (full kharif + anomaly)
  2. Sub-window features for 3 phenological periods:
     - Jun–Jul  (sowing + early vegetative)
     - Aug–Sep  (flowering + pod formation)
     - Oct      (maturity + harvest)
     Per window: NDVI, rainfall, SMAP SM, SAR VH

All batched into a SINGLE GEE getInfo() per RC-year for efficiency.
277 RCs × 8 years = 2,216 RC-years.

Usage:
    source .venv/bin/activate
    python3 -u scripts/extract_chf_features.py 2>&1 | tee logs/extract_chf.log
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
ALL_YEARS    = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
BUFFER_M     = 5000
SCALE_M      = 1000
N_WORKERS    = 10

SUB_WINDOWS = {
    'junjul': ('06-01', '07-31'),
    'augsep': ('08-01', '09-30'),
    'oct':    ('10-01', '10-31'),
}
KHARIF = ('06-01', '10-31')

YAVATMAL_COORDS = Path('data/processed/yavatmal_rc_coords.csv')
NEW_COORDS      = Path('data/processed/new_districts_rc_coords.csv')
PARTIAL         = Path('data/processed/chf_features_partial.csv')
OUT             = Path('data/processed/chf_features_all_districts.csv')

# ── GEE auth ──────────────────────────────────────────────────────────────────
try:
    ee.Initialize(project=GEE_PROJECT)
    print('GEE initialised.', flush=True)
except Exception:
    ee.Authenticate()
    ee.Initialize(project=GEE_PROJECT)
    print('GEE authenticated + initialised.', flush=True)

# ── Baselines (built once, reused across threads) ─────────────────────────────
print('Building baselines...', flush=True)
BASE_WINDOW = ('2003-01-01', '2026-01-01')

FAPAR_BASE = (ee.ImageCollection('MODIS/061/MCD15A3H')
                .select('Fpar')
                .filter(ee.Filter.calendarRange(6, 10, 'month'))
                .filter(ee.Filter.date(*BASE_WINDOW))
                .mean()
                .multiply(0.01))

NDVI_BASE = (ee.ImageCollection('MODIS/061/MOD13A2')
               .select('NDVI')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date(*BASE_WINDOW))
               .mean()
               .multiply(0.0001))

print('Baselines ready.', flush=True)


def safe_reduce(img, aoi, scale=SCALE_M):
    return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)


def extract_chf(lat, lon, year):
    """Extract FAPAR + sub-window features in one batched GEE call."""
    pt  = ee.Geometry.Point([lon, lat])
    aoi = pt.buffer(BUFFER_M)

    kh_start = f'{year}-{KHARIF[0]}'
    kh_end   = f'{year}-{KHARIF[1]}'

    result = {}

    # ── FAPAR (full kharif) ───────────────────────────────────────────────────
    fapar_col = (ee.ImageCollection('MODIS/061/MCD15A3H')
                   .select('Fpar')
                   .filter(ee.Filter.date(kh_start, kh_end))
                   .map(lambda i: i.multiply(0.01)))

    has_fapar = fapar_col.size().gt(0)
    fapar_null = FAPAR_BASE.updateMask(ee.Image(0))
    fapar_mean_img = ee.Image(ee.Algorithms.If(has_fapar, fapar_col.mean(), fapar_null))
    fapar_anom_img = ee.Image(ee.Algorithms.If(has_fapar,
                              fapar_col.mean().subtract(FAPAR_BASE), fapar_null))

    fm = safe_reduce(fapar_mean_img, aoi)
    fa = safe_reduce(fapar_anom_img, aoi)
    result['FAPAR_mean'] = ee.Algorithms.If(fm.contains('Fpar'), fm.get('Fpar'), None)
    result['FAPAR_anom'] = ee.Algorithms.If(fa.contains('Fpar'), fa.get('Fpar'), None)

    # ── Full-kharif NDVI anomaly ──────────────────────────────────────────────
    ndvi_col = (ee.ImageCollection('MODIS/061/MOD13A2')
                  .select('NDVI')
                  .filter(ee.Filter.date(kh_start, kh_end))
                  .map(lambda i: i.multiply(0.0001)))
    has_ndvi = ndvi_col.size().gt(0)
    ndvi_null = NDVI_BASE.updateMask(ee.Image(0))
    ndvi_anom_img = ee.Image(ee.Algorithms.If(has_ndvi,
                              ndvi_col.mean().subtract(NDVI_BASE), ndvi_null))
    na = safe_reduce(ndvi_anom_img, aoi)
    result['NDVI_anom_full'] = ee.Algorithms.If(na.contains('NDVI'), na.get('NDVI'), None)

    # ── Sub-window features ───────────────────────────────────────────────────
    for wname, (w_start_md, w_end_md) in SUB_WINDOWS.items():
        w_start = f'{year}-{w_start_md}'
        w_end   = f'{year}-{w_end_md}'

        # NDVI (MODIS 16-day)
        sw_ndvi = (ee.ImageCollection('MODIS/061/MOD13A2')
                     .select('NDVI')
                     .filter(ee.Filter.date(w_start, w_end))
                     .map(lambda i: i.multiply(0.0001)))
        has_n = sw_ndvi.size().gt(0)
        n_img = ee.Image(ee.Algorithms.If(has_n, sw_ndvi.mean(), ndvi_null))
        nr = safe_reduce(n_img, aoi)
        result[f'NDVI_{wname}'] = ee.Algorithms.If(nr.contains('NDVI'), nr.get('NDVI'), None)

        # Rainfall (CHIRPS daily → sum)
        sw_rain = (ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
                     .select('precipitation')
                     .filter(ee.Filter.date(w_start, w_end)))
        has_r = sw_rain.size().gt(0)
        rain_null = ee.Image(0).rename('precipitation').updateMask(ee.Image(0))
        r_img = ee.Image(ee.Algorithms.If(has_r, sw_rain.sum(), rain_null))
        rr = safe_reduce(r_img, aoi)
        result[f'rain_{wname}_mm'] = ee.Algorithms.If(
            rr.contains('precipitation'), rr.get('precipitation'), None)

        # SMAP soil moisture (9km)
        sw_smap = (ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006')
                     .select('soil_moisture_am')
                     .filter(ee.Filter.date(w_start, w_end)))
        has_s = sw_smap.size().gt(0)
        sm_null = ee.Image(0).rename('soil_moisture_am').updateMask(ee.Image(0))
        s_img = ee.Image(ee.Algorithms.If(has_s, sw_smap.mean(), sm_null))
        sr = safe_reduce(s_img, aoi)
        result[f'SM_{wname}'] = ee.Algorithms.If(
            sr.contains('soil_moisture_am'), sr.get('soil_moisture_am'), None)

        # SAR VH (Sentinel-1)
        sw_sar = (ee.ImageCollection('COPERNICUS/S1_GRD')
                    .filter(ee.Filter.eq('instrumentMode', 'IW'))
                    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
                    .filter(ee.Filter.date(w_start, w_end))
                    .select('VH'))
        has_v = sw_sar.size().gt(0)
        vh_null = ee.Image(0).rename('VH').updateMask(ee.Image(0))
        v_img = ee.Image(ee.Algorithms.If(has_v, sw_sar.mean(), vh_null))
        vr = safe_reduce(v_img, aoi)
        result[f'SAR_VH_{wname}_dB'] = ee.Algorithms.If(
            vr.contains('VH'), vr.get('VH'), None)

    return ee.Dictionary(result).getInfo()


def process_one(item):
    dist, tal, rc, lat, lon, yr = item
    for attempt in range(3):
        try:
            feats = extract_chf(lat, lon, yr)
            feats.update({'district': dist, 'taluka': tal, 'revenue_circle': rc,
                          'lat': lat, 'lon': lon, 'year': yr})
            return feats
        except Exception as e:
            time.sleep(5 * (attempt + 1))
    # all attempts failed
    feats = {'district': dist, 'taluka': tal, 'revenue_circle': rc,
             'lat': lat, 'lon': lon, 'year': yr}
    return feats


# ── Load all coords ───────────────────────────────────────────────────────────
yav = pd.read_csv(YAVATMAL_COORDS).dropna(subset=['lat', 'lon'])
yav['district'] = 'Yavatmal'
new = pd.read_csv(NEW_COORDS).dropna(subset=['lat', 'lon'])
all_coords = pd.concat([yav, new], ignore_index=True)
print(f"Total RCs: {len(all_coords)} ({len(yav)} Yavatmal + {len(new)} new)", flush=True)

# ── Load checkpoint ───────────────────────────────────────────────────────────
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
print(f"Remaining: {len(work)}/{total} RC-years. Using {N_WORKERS} workers.", flush=True)

# ── Parallel extraction ───────────────────────────────────────────────────────
lock = threading.Lock()
completed = 0

with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
    futures = {executor.submit(process_one, item): item for item in work}
    for future in as_completed(futures):
        result = future.result()
        with lock:
            partial_rows.append(result)
            completed += 1
            pct = (len(done_keys) + completed) / total * 100
            fapar = result.get('FAPAR_mean') or 0
            ndvi_as = result.get('NDVI_augsep') or 0
            rain_as = result.get('rain_augsep_mm') or 0
            print(f"[{len(done_keys)+completed}/{total}] "
                  f"{result['district']}/{result['revenue_circle']}/{result['year']}: "
                  f"FAPAR={fapar:.3f} "
                  f"NDVI_as={ndvi_as:.3f} "
                  f"Rain_as={rain_as:.0f}mm "
                  f"({pct:.1f}%)", flush=True)
            if completed % 50 == 0:
                df_tmp = pd.DataFrame(partial_rows)
                df_tmp.to_csv(PARTIAL, index=False)
                print(f"  ── checkpoint ({len(partial_rows)} rows) ──", flush=True)

# ── Final save ────────────────────────────────────────────────────────────────
final = pd.DataFrame(partial_rows)
final.to_csv(OUT, index=False)
print(f"\n✓ Done: {len(final)} rows → {OUT}", flush=True)
