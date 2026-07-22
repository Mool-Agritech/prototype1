"""
Geocode all 110 Yavatmal revenue circles using Nominatim (direct requests).
Falls back to taluka centroid if the specific village isn't found.
Outputs: yavatmal_rc_coords.csv
"""

import pandas as pd
import requests
import time
import sys

df = pd.read_csv("pmfby_yavatmal_iu_kharif.csv")
unique = (df[["taluka", "revenue_circle"]]
          .drop_duplicates()
          .sort_values(["taluka", "revenue_circle"])
          .reset_index(drop=True))

HEADERS = {"User-Agent": "mool-gcl26-pmfby-v5"}

def geocode(query):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=10,
        )
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"  HTTP error for '{query}': {e}", flush=True)
    return None, None

results = []
for i, row in unique.iterrows():
    taluka = row["taluka"]
    rc     = row["revenue_circle"]

    queries = [
        (f"{rc}, Yavatmal, Maharashtra",         "ok"),
        (f"{rc}, {taluka}, Maharashtra, India",  "fallback_taluka_state"),
        (f"{taluka}, Yavatmal, Maharashtra",      "fallback_taluka"),
    ]

    lat = lon = flag = None
    for q, flg in queries:
        lat, lon = geocode(q)
        if lat is not None:
            flag = flg
            break
        time.sleep(1.1)

    if flag is None:
        flag = "NOT_FOUND"
    sym = "✓" if lat else "✗"
    coord_str = f"{lat:.4f},{lon:.4f}" if lat else "NOT FOUND"
    print(f"[{i+1:03d}/110] {sym} {taluka}/{rc}: {coord_str} [{flag}]", flush=True)

    results.append({"taluka": taluka, "revenue_circle": rc, "lat": lat, "lon": lon, "geocode_flag": flag})
    time.sleep(1.1)

out = pd.DataFrame(results)
out.to_csv("yavatmal_rc_coords.csv", index=False)
found = out["lat"].notna().sum()
print(f"\nGeocoded {found}/{len(out)} revenue circles → yavatmal_rc_coords.csv")
print(f"Breakdown: {out['geocode_flag'].value_counts().to_dict()}")
