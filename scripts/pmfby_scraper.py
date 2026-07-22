"""
PMFBY IU-Level Scraper — Yavatmal district, all talukas, kharif 2021–2025
Outputs: pmfby_yavatmal_iu_kharif.csv

Strategy: for each (year, taluka), navigate fresh from state level to avoid stale elements.
"""

import asyncio
import csv
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

BASE_URL       = "https://pmfby.gov.in/adminStatistics/dashboard"
TARGET_STATE   = "MAHARASHTRA"
TARGET_DISTRICT= "Yavatmal"
SEASON         = "Kharif"
YEARS          = [2021, 2022, 2023, 2024, 2025]
OUT_FILE       = Path("data/raw/pmfby_yavatmal_iu_kharif.csv")

COLS = [
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


def clean(val: str) -> str:
    return re.sub(r"[,\s]+", "", val.strip()) or "0"


async def wait_table(page, need_links=True, timeout=15000):
    """Wait for the table to populate. need_links=False for the IU (leaf) level."""
    selector = "table tbody tr td a" if need_links else "table tbody tr td"
    await page.wait_for_selector(selector, timeout=timeout)
    await page.wait_for_timeout(500)


async def extract_table(page) -> list[dict]:
    """Extract rows that match the expected column count."""
    rows = await page.query_selector_all("table tbody tr")
    records = []
    for row in rows:
        cells = await row.query_selector_all("td")
        values = [clean(await c.inner_text()) for c in cells]
        if len(values) == len(COLS):
            records.append(dict(zip(COLS, values)))
    return records


async def nav_to_yavatmal(page, year: int):
    """Navigate from dashboard root → State Wise Report → set year/season → MH → Yavatmal."""
    await page.goto(BASE_URL, wait_until="networkidle")
    await page.wait_for_timeout(1200)
    await page.click("a:has-text('State Wise Report')", timeout=6000)
    await page.wait_for_timeout(1000)

    selects = await page.query_selector_all("select.form-control")
    await selects[0].select_option(str(year))
    await page.wait_for_timeout(300)
    await selects[1].select_option(SEASON)
    await page.wait_for_timeout(900)

    await wait_table(page)
    await page.click(f"a:has-text('{TARGET_STATE}')", timeout=8000)
    await wait_table(page)
    await page.click(f"a:has-text('{TARGET_DISTRICT}')", timeout=8000)
    await wait_table(page)


async def get_taluka_list(page) -> list[str]:
    els = await page.query_selector_all("table tbody tr td a")
    return [t.strip() for el in els if (t := await el.inner_text()).strip()]


async def scrape_taluka(page, year: int, taluka: str) -> list[dict]:
    """Fresh navigation to the taluka's IU table."""
    await nav_to_yavatmal(page, year)
    await page.click(f"a:has-text('{taluka}')", timeout=8000)
    await wait_table(page, need_links=False, timeout=12000)
    records = await extract_table(page)
    for r in records:
        r.update({"year": year, "season": SEASON,
                  "district": TARGET_DISTRICT, "taluka": taluka})
    return records


async def main():
    all_data = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page   = await browser.new_page(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )

        # Step 1: get the taluka list once (it's the same across years)
        print("Getting taluka list for Yavatmal...")
        await nav_to_yavatmal(page, 2024)
        talukas = await get_taluka_list(page)
        print(f"Found {len(talukas)} talukas: {talukas}")

        # Step 2: iterate year × taluka
        for year in YEARS:
            print(f"\n{'='*55}\nYear: {year}")
            year_records = []
            for taluka in talukas:
                print(f"  → {taluka}...", end="", flush=True)
                try:
                    records = await scrape_taluka(page, year, taluka)
                    year_records.extend(records)
                    print(f" {len(records)} IUs")
                except (PWTimeout, Exception) as e:
                    print(f" ERROR: {e}")
            print(f"  Year {year} total: {len(year_records)} IU-records")
            all_data.extend(year_records)

        await browser.close()

    # Write CSV
    if all_data:
        fieldnames = ["year", "season", "district", "taluka"] + COLS
        with open(OUT_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_data)
        print(f"\n✓ Saved {len(all_data)} rows → {OUT_FILE}")
    else:
        print("\nNo data collected.")


if __name__ == "__main__":
    asyncio.run(main())
