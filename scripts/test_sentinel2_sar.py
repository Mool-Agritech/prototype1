"""
test_sentinel2_sar.py
──────────────────────
Small feasibility test: does Sentinel-2 optical (10m) add usable signal
alongside Sentinel-1 SAR during Kharif season, given monsoon cloud cover?

Tests on a handful of RCs for 2023 (a recent, clear-ish year) and 2019
(a known wet/flood year) to see how cloud cover changes availability.
"""
import ee
import pandas as pd
import time

ee.Initialize(project='earth-mrv')

# Sample RCs: one per district
TEST_POINTS = [
    ('Yavatmal',   20.40, 78.11),
    ('Amravati',   20.93, 77.75),
    ('Chandrapur', 19.95, 79.30),
    ('Wardha',     20.75, 78.60),
]

TEST_YEARS = [2019, 2023]  # 2019 = wet/flood year, 2023 = drier year
BUFFER_M = 2500  # smaller buffer for 10m-scale test

def s2_cloud_stats(lat, lon, year):
    """Check S2 scene availability + cloud-free fraction during Kharif."""
    pt = ee.Geometry.Point([lon, lat])
    aoi = pt.buffer(BUFFER_M)
    start, end = f'{year}-06-01', f'{year}-10-31'

    s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(aoi)
            .filterDate(start, end))
    n_scenes = s2.size().getInfo()

    s2_clouds = (ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
                   .filterBounds(aoi)
                   .filterDate(start, end))

    # join cloud prob and compute per-scene clear fraction over AOI
    def add_clear_frac(img):
        idx = img.get('system:index')
        cloud_img = ee.Image(s2_clouds.filter(ee.Filter.eq('system:index', idx)).first())
        is_clear = cloud_img.select('probability').lt(40)
        clear_frac = is_clear.reduceRegion(ee.Reducer.mean(), aoi, 20, maxPixels=1e8).get('probability')
        return img.set('clear_frac', clear_frac)

    s2_with_clear = s2.map(add_clear_frac)
    clear_fracs = s2_with_clear.aggregate_array('clear_frac').getInfo()
    clear_fracs = [c for c in clear_fracs if c is not None]
    usable_scenes = sum(1 for c in clear_fracs if c > 0.7)

    # NDVI mean composite using only clear pixels
    def mask_clouds(img):
        idx = img.get('system:index')
        cloud_img = ee.Image(s2_clouds.filter(ee.Filter.eq('system:index', idx)).first())
        mask = cloud_img.select('probability').lt(40)
        return img.updateMask(mask)

    ndvi_col = s2.map(mask_clouds).map(
        lambda i: i.normalizedDifference(['B8', 'B4']).rename('NDVI'))
    ndvi_count = ndvi_col.select('NDVI').count().reduceRegion(
        ee.Reducer.mean(), aoi, 10, maxPixels=1e8).get('NDVI')
    ndvi_mean = ndvi_col.mean().reduceRegion(
        ee.Reducer.mean(), aoi, 10, maxPixels=1e8).get('NDVI')
    ndvi_std = ndvi_col.mean().reduceRegion(
        ee.Reducer.stdDev(), aoi, 10, maxPixels=1e8).get('NDVI')

    return {
        'n_scenes_total': n_scenes,
        'n_scenes_usable_70pct_clear': usable_scenes,
        'mean_clear_frac': sum(clear_fracs)/len(clear_fracs) if clear_fracs else 0,
        'ndvi_valid_obs_per_pixel': ndvi_count.getInfo() if ndvi_count else None,
        'S2_NDVI_mean': ndvi_mean.getInfo() if ndvi_mean else None,
        'S2_NDVI_std_within_field': ndvi_std.getInfo() if ndvi_std else None,
    }


def sar_stats(lat, lon, year):
    """SAR VH mean + within-AOI spatial std (texture proxy) for comparison."""
    pt = ee.Geometry.Point([lon, lat])
    aoi = pt.buffer(BUFFER_M)
    start, end = f'{year}-06-01', f'{year}-10-31'

    s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            .filterBounds(aoi)
            .filterDate(start, end)
            .select('VH'))
    n_scenes = s1.size().getInfo()
    vh_mean = s1.mean().reduceRegion(ee.Reducer.mean(), aoi, 10, maxPixels=1e8).get('VH')
    vh_std = s1.mean().reduceRegion(ee.Reducer.stdDev(), aoi, 10, maxPixels=1e8).get('VH')

    return {
        'n_s1_scenes': n_scenes,
        'S1_VH_mean_dB': vh_mean.getInfo() if vh_mean else None,
        'S1_VH_std_within_field_dB': vh_std.getInfo() if vh_std else None,
    }


rows = []
for dist, lat, lon in TEST_POINTS:
    for yr in TEST_YEARS:
        print(f'Testing {dist} {yr}...', flush=True)
        t0 = time.time()
        row = {'district': dist, 'year': yr}
        try:
            row.update(s2_cloud_stats(lat, lon, yr))
        except Exception as e:
            print(f'  S2 error: {str(e)[:150]}', flush=True)
        try:
            row.update(sar_stats(lat, lon, yr))
        except Exception as e:
            print(f'  SAR error: {str(e)[:150]}', flush=True)
        row['elapsed_s'] = round(time.time() - t0, 1)
        rows.append(row)
        print(f'  -> {row}', flush=True)

df = pd.DataFrame(rows)
df.to_csv('data/processed/s2_sar_feasibility_test.csv', index=False)
print('\nSaved -> data/processed/s2_sar_feasibility_test.csv')
print(df.to_string(index=False))
