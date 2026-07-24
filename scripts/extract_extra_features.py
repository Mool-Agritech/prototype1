"""
extract_extra_features.py
─────────────────────────
Extracts 3 additional features using a PARALLEL thread pool:
  - MODIS ET anomaly   (MOD16A2, 8-day, 500m)
  - SMAP surface SM    (SPL3SMP_E, 9km, 2015-present)
  - Sentinel-1 SAR VH  (IW mode, cross-pol)

Covers ALL 4 districts (Yavatmal + Amravati + Wardha + Chandrapur),
277 RCs × 8 years = 2,216 RC-years.

Usage:
    source .venv/bin/activate
    python3 -u scripts/extract_extra_features.py 2>&1 | tee logs/extract_extra.log
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
KHARIF_START = '06-01'
KHARIF_END   = '10-31'
BASE_WINDOW  = ('2016-01-01', '2026-01-01')
N_WORKERS    = 10   # parallel GEE calls

YAVATMAL_COORDS = Path('data/processed/yavatmal_rc_coords.csv')
NEW_COORDS      = Path('data/processed/new_districts_rc_coords.csv')
PARTIAL         = Path('data/processed/extra_features_partial.csv')
OUT             = Path('data/processed/extra_features_all_districts.csv')

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

ET_BASE = (ee.ImageCollection('MODIS/061/MOD16A2')
             .select('ET')
             .filter(ee.Filter.calendarRange(6, 10, 'month'))
             .filter(ee.Filter.date(*BASE_WINDOW))
             .mean()
             .multiply(0.1))

SMAP_BASE = (ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006')
               .select('soil_moisture_am')
               .filter(ee.Filter.calendarRange(6, 10, 'month'))
               .filter(ee.Filter.date('2016-01-01', '2026-01-01'))
               .mean())

print('Baselines ready.', flush=True)


def safe_mean(collection, baseline_img):
    has_data = collection.size().gt(0)
    null_img = baseline_img.updateMask(ee.Image(0))
    mean_img = ee.Image(ee.Algorithms.If(has_data, collection.mean(), null_img))
    anom_img = ee.Image(ee.Algorithms.If(has_data,
                         collection.mean().subtract(baseline_img), null_img))
    return mean_img, anom_img


def extract_extra(lat, lon, year):
    pt    = ee.Geometry.Point([lon, lat])
    aoi   = pt.buffer(BUFFER_M)
    start = f'{year}-{KHARIF_START}'
    end   = f'{year}-{KHARIF_END}'

    def red(img, scale=SCALE_M):
        return img.reduceRegion(ee.Reducer.mean(), aoi, scale, maxPixels=1e7)

    # MODIS ET
    et_col = (ee.ImageCollection('MODIS/061/MOD16A2')
                .select('ET')
                .filter(ee.Filter.date(start, end))
                .map(lambda i: i.multiply(0.1)))
    et_mean_img, et_anom_img = safe_mean(et_col, ET_BASE)
    et_mean = red(et_mean_img)
    et_anom = red(et_anom_img)

    # SMAP
    smap_col = (ee.ImageCollection('NASA/SMAP/SPL3SMP_E/006')
                  .select('soil_moisture_am')
                  .filter(ee.Filter.date(start, end)))
    smap_mean_img, smap_anom_img = safe_mean(smap_col, SMAP_BASE)
    smap_mean = red(smap_mean_img)
    smap_anom = red(smap_anom_img)

    # Sentinel-1 SAR
    s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            .filter(ee.Filter.date(start, end))
            .select(['VV', 'VH']))
    s1_null = ee.Image(0).rename('VH').updateMask(ee.Image(0))
    has_s1  = s1.size().gt(0)
    sar_vh  = red(ee.Image(ee.Algorithms.If(has_s1, s1.select('VH').mean(), s1_null)))
    s1_cr   = s1.map(lambda i: i.select('VH').subtract(i.select('VV')).rename('CR'))
    sar_cr  = red(ee.Image(ee.Algorithms.If(has_s1, s1_cr.mean(),
                            ee.Image(0).rename('CR').updateMask(ee.Image(0)))))

    def safe_get(d, key):
        return ee.Algorithms.If(d.contains(key), d.get(key), None)

    result = ee.Dictionary({
        'ET_mean_mm8d':   safe_get(et_mean,   'ET'),
        'ET_anom_mm8d':   safe_get(et_anom,   'ET'),
        'SMAP_sm_mean':   safe_get(smap_mean, 'soil_moisture_am'),
        'SMAP_sm_anom':   safe_get(smap_anom, 'soil_moisture_am'),
        'SAR_VH_mean_dB': safe_get(sar_vh,    'VH'),
        'SAR_CR_mean_dB': safe_get(sar_cr,    'CR'),
    })
    return result.getInfo()


def process_one(item):
    dist, tal, rc, lat, lon, yr = item
    for attempt in range(3):
        try:
            feats = extract_extra(lat, lon, yr)
            feats.update({'district': dist, 'taluka': tal, 'revenue_circle': rc,
                          'lat': lat, 'lon': lon, 'year': yr})
            return feats
        except Exception as e:
            time.sleep(5 * (attempt + 1))
    # all attempts failed — return NaN row
    return {'district': dist, 'taluka': tal, 'revenue_circle': rc,
            'lat': lat, 'lon': lon, 'year': yr,
            'ET_mean_mm8d': None, 'ET_anom_mm8d': None,
            'SMAP_sm_mean': None, 'SMAP_sm_anom': None,
            'SAR_VH_mean_dB': None, 'SAR_CR_mean_dB': None}


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
print(f"Remaining: {len(work)}/{total} RC-years. Using {N_WORKERS} parallel workers.", flush=True)

# ── Parallel extraction ───────────────────────────────────────────────────────
FIELDS = ['district', 'taluka', 'revenue_circle', 'lat', 'lon', 'year',
          'ET_mean_mm8d', 'ET_anom_mm8d', 'SMAP_sm_mean', 'SMAP_sm_anom',
          'SAR_VH_mean_dB', 'SAR_CR_mean_dB']

lock = threading.Lock()
completed = 0

with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
    futures = {executor.submit(process_one, item): item for item in work}
    for future in as_completed(futures):
        result = future.result()
        with lock:
            partial_rows.append(result)
            completed += 1
            item = futures[future]
            pct = (len(done_keys) + completed) / total * 100
            print(f"[{len(done_keys)+completed}/{total}] "
                  f"{result['district']}/{result['revenue_circle']}/{result['year']}: "
                  f"ET={result.get('ET_mean_mm8d') or 0:.1f} "
                  f"SMAP={result.get('SMAP_sm_mean') or 0:.3f} "
                  f"VH={result.get('SAR_VH_mean_dB') or 0:.1f}dB "
                  f"({pct:.1f}%)", flush=True)
            # checkpoint every 50 rows
            if completed % 50 == 0:
                df_tmp = pd.DataFrame(partial_rows)
                for c in FIELDS:
                    if c not in df_tmp.columns:
                        df_tmp[c] = np.nan
                df_tmp[FIELDS].to_csv(PARTIAL, index=False)
                print(f"  ── checkpoint ({len(partial_rows)} rows) ──", flush=True)

# ── Final save ────────────────────────────────────────────────────────────────
final = pd.DataFrame(partial_rows)
for c in FIELDS:
    if c not in final.columns:
        final[c] = np.nan
final[FIELDS].to_csv(OUT, index=False)
print(f"\n✓ Done: {len(final)} rows → {OUT}", flush=True)
