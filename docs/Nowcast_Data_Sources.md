# Nowcast Data Sources — Mool

> All sources relevant to the parametric trigger nowcast. Backtest uses the same sources where historical depth exists.

---

## Rainfall & Water Deficit


| Source              | Variable                     | Resolution | Cadence | Lag      | Access    | Nowcast Role                                             |
| ------------------- | ---------------------------- | ---------- | ------- | -------- | --------- | -------------------------------------------------------- |
| **CHIRPS**          | Daily precipitation          | 5 km       | Daily   | ~5 days  | GEE, free | Rolling 30/60-day rainfall deficit vs. historical normal |
| **GPM IMERG Early** | Near-real-time precipitation | 10 km      | 30 min  | ~6 hours | GEE, free | Same-day rainfall signal; faster than CHIRPS             |
| **ERA5-Land**       | Precip, evaporation          | 9 km       | Daily   | ~5 days  | GEE, free | Backup rainfall + actual evapotranspiration              |


---



## Crop Health & Vegetation


| Source                                      | Variable                      | Resolution | Cadence                                          | Lag      | Access                        | Nowcast Role                                                                          |
| ------------------------------------------- | ----------------------------- | ---------- | ------------------------------------------------ | -------- | ----------------------------- | ------------------------------------------------------------------------------------- |
| **Sentinel-2 SR**                           | NDVI, EVI, NDRE, SWIR indices | 10–20 m    | ~5 days                                          | 1–2 days | GEE, free                     | Primary optical crop stress signal; cloud-limited during monsoon                      |
| **AWIFS_BOA** (Bhoonidhi)                   | Green, Red, NIR, SWIR → NDVI  | 56 m       | ~5 days when cloud-free                          | 1–2 days | Bhoonidhi API, whitelisted IP | **PMFBY-aligned sensor** — trigger calibrated on same data as government adjudication |
| **AWIFS 15-day NDVI composite** (Bhoonidhi) | Cloud-minimised NDVI mosaic   | 100 m      | 15 days                                          | ~2 days  | Bhoonidhi API, whitelisted IP | **Best cloud-robust NDVI for monsoon season** — directly usable as trigger input      |
| **LISS3_L2** (Bhoonidhi)                    | Green, Red, NIR, SWIR         | 23.5 m     | ~24-day repeat; 100+ scenes/season over Vidarbha | 1–2 days | Bhoonidhi API, whitelisted IP | Fine-resolution crop discrimination; cross-validates AWIFS                            |
| **MODIS MOD13Q1**                           | 16-day NDVI/EVI composite     | 250 m      | 16 days                                          | ~2 days  | GEE, free                     | Long historical baseline (2000–present); cloud-free composite; fills S2 gaps          |
| **VIIRS VNP13A1**                           | 16-day NDVI/EVI               | 500 m      | 16 days                                          | ~2 days  | GEE, free                     | Higher-frequency backup to MODIS, newer sensor                                        |


---



## Soil Moisture & Heat Stress


| Source                  | Variable                                             | Resolution | Cadence | Lag     | Access    | Nowcast Role                                                                   |
| ----------------------- | ---------------------------------------------------- | ---------- | ------- | ------- | --------- | ------------------------------------------------------------------------------ |
| **ERA5-Land**           | Soil moisture (3 layers), temp, VPD, solar radiation | 9 km       | Daily   | ~5 days | GEE, free | Core heat/drought stress variables; VPD is the best single crop-stress scalar  |
| **SMAP L3**             | Surface + root-zone soil moisture                    | 36 km      | Daily   | ~3 days | GEE, free | Independent soil moisture validation; coarse but direct microwave measurement  |
| **MODIS LST (MOD11A2)** | Land surface temperature                             | 1 km       | 8 days  | ~2 days | GEE, free | Heat stress proxy; catches localised temperature anomalies ERA5 misses at 9 km |


---



## SAR / All-Weather


| Source                          | Variable                  | Resolution | Cadence       | Lag     | Access                        | Nowcast Role                                                                                       |
| ------------------------------- | ------------------------- | ---------- | ------------- | ------- | ----------------------------- | -------------------------------------------------------------------------------------------------- |
| **Sentinel-1 GRD**              | VV, VH backscatter        | 10 m       | 6–12 days     | 1 day   | GEE, free                     | Cloud-penetrating crop structure + soil moisture proxy; critical during monsoon when optical fails |
| **NISAR SSAR GUNW** (Bhoonidhi) | InSAR ground displacement | 5.6 m      | 12-day repeat | ~3 days | Bhoonidhi API, whitelisted IP | Subsurface irrigation stress, crop height change, waterlogging detection — data starts July 2026   |


---



## Topography (Static)


| Source                         | Variable                 | Resolution | Access                        | Nowcast Role                                                                                                       |
| ------------------------------ | ------------------------ | ---------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **CartoSat-1 DEM** (Bhoonidhi) | Elevation, slope, aspect | 30 m       | Bhoonidhi API, whitelisted IP | Permanent drainage/waterlogging risk modifier for plot-level scoring; 18 tiles cover all of Vidarbha, all Online=Y |
| **SRTM DEM**                   | Elevation, slope         | 30 m       | GEE, free                     | Fallback if CartoSat unavailable; slightly older but identical use                                                 |


---



## Trigger Logic

The arithmetic nowcast stacks sources in three layers:

**1. Stress signal** — updated every 15 days
AWIFS 15-day NDVI composite or Sentinel-2 NDVI → compute anomaly against MODIS/S2 historical median for that calendar week.

**2. Forcing signal** — updated every few days
GPM IMERG rolling 30-day rainfall deficit + ERA5 VPD current value → determines whether stress is drought-driven, heat-driven, or both.

**3. Permanent risk modifier** — static
CartoSat DEM slope → adjusts trigger threshold per plot based on drainage characteristics.

**Trigger condition:**
`NDVI anomaly ≤ −X%` AND `rainfall deficit ≥ Y mm` AND `VPD ≥ Z kPa` → payout triggered.

---



## Access Notes


| Access type                       | What it means                                                                                                                           |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **GEE, free**                     | Google Earth Engine — works from any IP, just needs a GEE-authorised Google account                                                     |
| **Bhoonidhi API, whitelisted IP** | ISRO Bhoonidhi portal — requires static public IPv4 to be registered with NRSC at [bhoonidhi@nrsc.gov.in](mailto:bhoonidhi@nrsc.gov.in) |


To add a new IP, email: `bhoonidhi[at]nrsc[dot]gov[dot]in` with subject "Bhoonidhi API access - [username], [IP], /auth/token".