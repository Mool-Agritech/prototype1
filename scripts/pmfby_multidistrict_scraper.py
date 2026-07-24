"""
pmfby_multidistrict_scraper.py
──────────────────────────────
Extends the Yavatmal scraper to cover Amravati, Wardha, and Chandrapur —
same cotton/soybean Kharif crop mix, different rainfall regimes.

Strategy:
  - One output CSV per district (checkpointed)
  - Dynamically discovers taluka list from dashboard for each district/year
  - Uses a known-good fallback taluka list (from manual inspection) if
    the dashboard loads slowly / lists 0 links on first attempt
  - Re-uses the same 29-column schema as Yavatmal

Usage:
    source .venv/bin/activate
    python3 -u scripts/pmfby_multidistrict_scraper.py 2>&1 | tee logs/pmfby_multidistrict.log

Outputs (one per district):
    data/raw/pmfby_amravati_iu_kharif.csv
    data/raw/pmfby_wardha_iu_kharif.csv
    data/raw/pmfby_chandrapur_iu_kharif.csv
"""

import asyncio
import csv
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

BASE_URL = "https://pmfby.gov.in/adminStatistics/dashboard"
TARGET_STATE = "MAHARASHTRA"
SEASON = "Kharif"
YEARS  = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

# Known taluka lists as fallback (if dashboard loads 0 links on first attempt)
# Amravati: 14 talukas (confirmed from dashboard screenshot 2024)
# Wardha: 8 talukas (standard)
# Chandrapur: 15 talukas (standard)
KNOWN_TALUKAS = {
    "Amravati": [
        "Achalpur", "Amravati", "Anjangaon Surji", "Bhatkuli",
        "Chandur Railway", "Chandurabazar", "Chikhaldara", "Daryapur",
        "Dhamangaon Railway", "Dharni", "Morshi", "Nandgaon-Khandeshwar",
        "Teosa", "Warud",
    ],
    # Wardha: no IU drill-down on dashboard — data stops at taluka level
    # Scraped directly as rows (not as taluka links to click through)
    "Chandrapur": [
        "Ballarpur", "Bhadravati", "Brahmapuri", "Chandrapur", "Chimur",
        "Gondpipri", "Jiwati", "Korpana", "Mul", "Nagbhid",
        "Pombhurna", "Rajura", "Sawali", "Sindewahi", "Warora",
    ],
}

# Districts where data is at TALUKA level (no IU drill-down links)
# We scrape the taluka-aggregated rows directly
TALUKA_LEVEL_DISTRICTS = {"Wardha"}

DISTRICTS = {
    "Amravati":   Path("data/raw/pmfby_amravati_iu_kharif.csv"),
    "Wardha":     Path("data/raw/pmfby_wardha_iu_kharif.csv"),
    "Chandrapur": Path("data/raw/pmfby_chandrapur_iu_kharif.csv"),
}

COLS_29 = [
    "sno", "revenue_circle", "insurance_units", "farmers",
    "app_loanee", "app_non_loanee", "area_insured_hect",
    "farmers_premium_rs", "state_premium_rs", "goi_premium_rs", "gross_premium_rs",
    "sum_insured_rs",
    "gender_male", "gender_female", "gender_others",
    "cat_sc", "cat_st", "cat_obc", "cat_gen",
    "farmer_marginal", "farmer_small", "farmer_others",
    "claim_prevented_sowing", "claim_localized", "claim_midterm",
    "claim_yield_based", "claim_post_harvest", "claim_wbcis", "claim_total",
]
ALL_FIELDNAMES = ["year", "season", "district", "taluka", "col_count"] + COLS_29


def clean(val: str) -> str:
    return re.sub(r"[,\s]+", "", val.strip()) or "0"


def load_done_pairs(out_file: Path) -> set:
    done = set()
    if not out_file.exists():
        return done
    with open(out_file) as f:
        for row in csv.DictReader(f):
            done.add((int(row["year"]), row["taluka"]))
    return done


async def nav_to_district(page, year: int, district: str):
    await page.goto(BASE_URL, wait_until="networkidle")
    await page.wait_for_timeout(1200)
    await page.click("a:has-text('State Wise Report')", timeout=6000)
    await page.wait_for_timeout(1000)

    selects = await page.query_selector_all("select.form-control")
    await selects[0].select_option(str(year))
    await page.wait_for_timeout(500)
    await selects[1].select_option(SEASON)
    await page.wait_for_timeout(2000)

    await page.wait_for_selector("table tbody tr td a", timeout=12000)
    await page.click(f"a:has-text('{TARGET_STATE}')", timeout=8000)
    await page.wait_for_timeout(2000)
    await page.wait_for_selector("table tbody tr td a", timeout=12000)
    await page.click(f"a:has-text('{district}')", timeout=8000)
    await page.wait_for_timeout(2500)


async def get_taluka_list(page, district: str) -> list[str]:
    links = await page.query_selector_all("table tbody tr td a")
    talukas = [(await l.inner_text()).strip() for l in links if (await l.inner_text()).strip()]
    if not talukas:
        # Dashboard loaded slowly — use known fallback list
        talukas = KNOWN_TALUKAS.get(district, [])
        print(f"    (using known fallback taluka list for {district})")
    return talukas


async def extract_table(page) -> tuple[list[dict], int]:
    rows = await page.query_selector_all("table tbody tr")
    records = []
    observed = 0
    for row in rows:
        cells = await row.query_selector_all("td")
        values = [clean(await c.inner_text()) for c in cells]
        n = len(values)
        if n < 5:
            continue
        observed = max(observed, n)
        cols = COLS_29 if n == 29 else [f"col_{i}" for i in range(n)]
        rec = dict(zip(cols, values))
        rec["col_count"] = n
        for c in COLS_29:
            rec.setdefault(c, "")
        records.append(rec)
    return records, observed


async def scrape_wardha_taluka_level(out_file: Path):
    """Wardha has no IU drill-down — scrape taluka rows directly from the district table."""
    district = "Wardha"
    done_years = set()
    if out_file.exists() and out_file.stat().st_size > 0:
        with open(out_file) as f:
            for row in csv.DictReader(f):
                done_years.add(int(row["year"]))
    if done_years:
        print(f"  Resuming Wardha — years already done: {sorted(done_years)}")

    write_header = not out_file.exists() or out_file.stat().st_size == 0
    out_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(out_file, "a", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=ALL_FIELDNAMES, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")

        total_new = 0
        for year in YEARS:
            if year in done_years:
                print(f"  Wardha {year}: SKIPPED")
                continue
            print(f"  Wardha {year}...", end="", flush=True)
            try:
                await nav_to_district(page, year, district)
                records, col_count = await extract_table(page)
                # For taluka-level data, revenue_circle = taluka name
                for r in records:
                    r.update({"year": year, "season": SEASON, "district": district,
                               "taluka": r.get("revenue_circle", ""),
                               "col_count": r.get("col_count", col_count)})
                if records:
                    writer.writerows(records)
                    csv_file.flush()
                    total_new += len(records)
                    print(f" {len(records)} taluka rows")
                else:
                    print(f" 0 rows (no data for {year})")
            except Exception as e:
                print(f" ERROR: {str(e)[:80]}")

        await browser.close()

    csv_file.close()
    print(f"  ✓ Wardha done — {total_new} new rows → {out_file}")


async def scrape_district(district: str, out_file: Path):
    done_pairs = load_done_pairs(out_file)
    if done_pairs:
        print(f"  Resuming {district} — {len(done_pairs)} (year,taluka) pairs already done")

    write_header = not out_file.exists() or out_file.stat().st_size == 0
    out_file.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(out_file, "a", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=ALL_FIELDNAMES, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        # Get taluka list using most recent year with good data (2023)
        print(f"  Getting taluka list for {district}...")
        await nav_to_district(page, 2023, district)
        talukas = await get_taluka_list(page, district)
        print(f"  → {len(talukas)} talukas: {talukas}")

        total_new = 0
        for year in YEARS:
            print(f"\n  {'='*50}\n  {district} — Year: {year}")
            year_new = 0
            for taluka in talukas:
                if (year, taluka) in done_pairs:
                    print(f"    → {taluka}... SKIPPED")
                    continue
                print(f"    → {taluka}...", end="", flush=True)
                try:
                    await nav_to_district(page, year, district)
                    # Find the taluka link — try exact match first, then contains
                    try:
                        await page.click(f"a:has-text('{taluka}')", timeout=6000)
                    except PWTimeout:
                        print(f" (link not found for {year})", end="")
                        done_pairs.add((year, taluka))
                        continue
                    await page.wait_for_timeout(4000)
                    records, col_count = await extract_table(page)
                    for r in records:
                        r.update({"year": year, "season": SEASON,
                                  "district": district, "taluka": taluka,
                                  "col_count": r.get("col_count", col_count)})
                    if records:
                        writer.writerows(records)
                        csv_file.flush()
                        year_new += len(records)
                        total_new += len(records)
                        print(f" {len(records)} IUs (col={col_count})")
                    else:
                        print(f" 0 IUs (no data)")
                    done_pairs.add((year, taluka))
                except Exception as e:
                    print(f" ERROR: {str(e)[:80]}")

            print(f"  {district} {year}: {year_new} new rows")

        await browser.close()

    csv_file.close()
    print(f"\n  ✓ {district} done — {total_new} total new rows → {out_file}")


async def main():
    for district, out_file in DISTRICTS.items():
        print(f"\n{'#'*60}")
        print(f"# DISTRICT: {district}")
        print(f"{'#'*60}")
        if district in TALUKA_LEVEL_DISTRICTS:
            await scrape_wardha_taluka_level(out_file)
        else:
            await scrape_district(district, out_file)

    # Summary
    print("\n\n=== SUMMARY ===")
    for district, out_file in DISTRICTS.items():
        if out_file.exists():
            done = load_done_pairs(out_file)
            print(f"  {district}: {len(done)} (year,taluka) pairs in {out_file.name}")


if __name__ == "__main__":
    asyncio.run(main())
