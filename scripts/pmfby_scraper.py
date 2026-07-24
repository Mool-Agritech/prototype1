"""
PMFBY IU-Level Scraper — Yavatmal district, all talukas, kharif 2016–2025
Outputs: pmfby_yavatmal_iu_kharif.csv

Strategy: for each (year, taluka), navigate fresh from state level to avoid stale elements.
Checkpointing: already-scraped (year, taluka) pairs are skipped on resume.
"""

import asyncio
import csv
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

BASE_URL        = "https://pmfby.gov.in/adminStatistics/dashboard"
TARGET_STATE    = "MAHARASHTRA"
TARGET_DISTRICT = "Yavatmal"
SEASON          = "Kharif"
# Dashboard goes back to 2018 (2016/2017 not available in dropdown)
YEARS           = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
OUT_FILE        = Path("data/raw/pmfby_yavatmal_iu_kharif.csv")

# Canonical 29-column schema (2021-2025 confirmed)
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

# Fallback schema for older years that may lack gender/category/farmer-size columns
# Discovered dynamically; kept here for reference if needed
COLS_MINIMAL = [
    "sno", "revenue_circle", "insurance_units", "farmers",
    "app_loanee", "app_non_loanee", "area_insured_hect",
    "farmers_premium_rs", "state_premium_rs", "goi_premium_rs", "gross_premium_rs",
    "sum_insured_rs",
    "claim_prevented_sowing", "claim_localized", "claim_midterm",
    "claim_yield_based", "claim_post_harvest", "claim_wbcis", "claim_total",
]

ALL_FIELDNAMES = ["year", "season", "district", "taluka", "col_count"] + COLS_29


def clean(val: str) -> str:
    return re.sub(r"[,\s]+", "", val.strip()) or "0"


def cols_for_count(n: int) -> list[str]:
    """Return the best-fit column list for a given cell count."""
    if n == 29:
        return COLS_29
    if n == 19:
        return COLS_MINIMAL
    # Unknown schema: use positional names so data isn't lost
    return [f"col_{i}" for i in range(n)]


async def wait_table(page, need_links=True, timeout=15000):
    """Wait for the table to populate. need_links=False for the IU (leaf) level."""
    selector = "table tbody tr td a" if need_links else "table tbody tr td"
    await page.wait_for_selector(selector, timeout=timeout)
    await page.wait_for_timeout(500)


async def extract_table(page) -> tuple[list[dict], int]:
    """Extract all rows; handle variable column counts across years.
    Returns (records, observed_col_count).
    """
    rows = await page.query_selector_all("table tbody tr")
    records = []
    observed_count = 0
    for row in rows:
        cells = await row.query_selector_all("td")
        values = [clean(await c.inner_text()) for c in cells]
        n = len(values)
        if n < 5:          # skip header-repeat or empty rows
            continue
        observed_count = max(observed_count, n)
        cols = cols_for_count(n)
        rec = dict(zip(cols, values))
        rec["col_count"] = n
        # Pad missing COLS_29 fields with "" so CSV schema is consistent
        for c in COLS_29:
            rec.setdefault(c, "")
        records.append(rec)
    return records, observed_count


def load_done_pairs(out_file: Path) -> set[tuple]:
    """Return set of (year, taluka) pairs already present in the CSV."""
    done = set()
    if not out_file.exists():
        return done
    with open(out_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add((int(row["year"]), row["taluka"]))
    return done


async def nav_to_yavatmal(page, year: int):
    """Navigate from dashboard root → State Wise Report → set year/season → MH → Yavatmal."""
    await page.goto(BASE_URL, wait_until="networkidle")
    await page.wait_for_timeout(1200)
    await page.click("a:has-text('State Wise Report')", timeout=6000)
    await page.wait_for_timeout(1000)

    selects = await page.query_selector_all("select.form-control")
    await selects[0].select_option(str(year))
    await page.wait_for_timeout(500)
    await selects[1].select_option(SEASON)
    await page.wait_for_timeout(2000)   # older years need more load time

    await wait_table(page)
    await page.click(f"a:has-text('{TARGET_STATE}')", timeout=8000)
    await page.wait_for_timeout(2000)
    await wait_table(page)
    await page.click(f"a:has-text('{TARGET_DISTRICT}')", timeout=8000)
    await page.wait_for_timeout(2000)
    await wait_table(page)


async def get_taluka_list(page) -> list[str]:
    els = await page.query_selector_all("table tbody tr td a")
    return [t.strip() for el in els if (t := await el.inner_text()).strip()]


async def scrape_taluka(page, year: int, taluka: str) -> list[dict]:
    """Fresh navigation to the taluka's IU table."""
    await nav_to_yavatmal(page, year)
    await page.click(f"a:has-text('{taluka}')", timeout=8000)
    await page.wait_for_timeout(4000)   # IU table needs extra load time (esp. older years)
    records, col_count = await extract_table(page)
    for r in records:
        r.update({"year": year, "season": SEASON,
                  "district": TARGET_DISTRICT, "taluka": taluka,
                  "col_count": r.get("col_count", col_count)})
    return records


async def main():
    # ── Checkpoint: skip already-done (year, taluka) pairs ───────────────────
    done_pairs = load_done_pairs(OUT_FILE)
    if done_pairs:
        print(f"Resuming — {len(done_pairs)} (year, taluka) pairs already scraped.")

    # Open CSV in append mode (write header only if file is new)
    write_header = not OUT_FILE.exists() or OUT_FILE.stat().st_size == 0
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(OUT_FILE, "a", newline="")
    writer = csv.DictWriter(csv_file, fieldnames=ALL_FIELDNAMES, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page   = await browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        # Step 1: get taluka list (use 2024 as reference; list is stable across years)
        print("Getting taluka list for Yavatmal...")
        await nav_to_yavatmal(page, 2024)
        talukas = await get_taluka_list(page)
        print(f"Found {len(talukas)} talukas: {talukas}")

        # Step 2: iterate year × taluka, skipping done pairs
        for year in YEARS:
            print(f"\n{'='*55}\nYear: {year}")
            year_new = 0
            for taluka in talukas:
                if (year, taluka) in done_pairs:
                    print(f"  → {taluka}... SKIPPED (already scraped)")
                    continue
                print(f"  → {taluka}...", end="", flush=True)
                try:
                    records = await scrape_taluka(page, year, taluka)
                    if records:
                        writer.writerows(records)
                        csv_file.flush()          # persist immediately
                        done_pairs.add((year, taluka))
                        year_new += len(records)
                        col_c = records[0].get("col_count", "?")
                        print(f" {len(records)} IUs (col_count={col_c})")
                    else:
                        print(f" 0 IUs (no data / year not available)")
                        done_pairs.add((year, taluka))   # mark done to avoid re-scraping empty
                except (PWTimeout, Exception) as e:
                    print(f" ERROR: {e}")
            print(f"  Year {year}: {year_new} new rows written")

        await browser.close()

    csv_file.close()
    # Count total rows
    done_pairs_final = load_done_pairs(OUT_FILE)
    print(f"\n✓ Done. {OUT_FILE} — {len(done_pairs_final)} (year, taluka) pairs total.")


if __name__ == "__main__":
    asyncio.run(main())
