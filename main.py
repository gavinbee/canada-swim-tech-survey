"""
main.py — orchestrator for the Canadian swim-club software survey.

Usage:
    python main.py [--limit N] [--no-cache] [--delay SECS]

Steps:
  1. Fetch club list from Swimming Canada (REST API + HTML fallback)
     and provincial association websites
  2. Visit each club's website and detect team management software
  3. Save raw results to data/clubs_raw.csv
  4. Save enriched results to data/results.csv
  5. Generate output/report.html with Chart.js visualisations
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from src.clubs import fetch_all_clubs
from src.detector import detect
from src.visualize import generate_html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path("data")
OUTPUT_DIR = Path("output")
RAW_CSV = DATA_DIR / "clubs_raw.csv"
RESULTS_CSV = DATA_DIR / "results.csv"
REPORT_HTML = OUTPUT_DIR / "report.html"


def _load_cached():
    if RESULTS_CSV.exists():
        df = pd.read_csv(RESULTS_CSV)
        log.info("Loaded %d cached results from %s", len(df), RESULTS_CSV)
        return df
    return None


def _save_raw(clubs):
    DATA_DIR.mkdir(exist_ok=True)
    fieldnames = ["name", "province", "province_name", "city", "website", "facebook", "members", "lat", "lng", "source"]
    with open(RAW_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(clubs)
    log.info("Saved raw club list → %s", RAW_CSV)


def _save_results(rows):
    DATA_DIR.mkdir(exist_ok=True)
    fieldnames = [
        "name", "province", "province_name", "city",
        "website", "facebook", "members", "lat", "lng", "source",
        "software", "category", "final_url", "error",
    ]
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log.info("Saved enriched results → %s", RESULTS_CSV)


def run(limit=None, use_cache=True, extra_delay=0.0):
    OUTPUT_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    # ----------------------------------------------------------------
    # Step 1: fetch clubs
    # ----------------------------------------------------------------
    log.info("=== Step 1: Fetching club list ===")
    clubs = fetch_all_clubs()

    if not clubs:
        log.error("No clubs found — check network access and Swimming Canada website.")
        sys.exit(1)

    _save_raw(clubs)

    if limit:
        clubs = clubs[:limit]
        log.info("Limiting to first %d clubs for this run", limit)

    # ----------------------------------------------------------------
    # Step 2: software detection
    # ----------------------------------------------------------------
    if use_cache and RESULTS_CSV.exists():
        df = _load_cached()
        # Only re-check clubs not already in cache
        done = set(df["website"].dropna().str.rstrip("/").str.lower())
        remaining = [c for c in clubs if c.get("website", "").rstrip("/").lower() not in done]
        rows = df.to_dict("records")
    else:
        remaining = clubs
        rows = []

    log.info("=== Step 2: Detecting software for %d clubs ===", len(remaining))

    for club in tqdm(remaining, unit="club", desc="Scanning"):
        if extra_delay:
            time.sleep(extra_delay)
        result = detect(club.get("website", ""))
        row = {**club, **result}
        rows.append(row)
        # Persist incrementally so a crash doesn't lose progress
        _save_results(rows)

    # ----------------------------------------------------------------
    # Step 3: reporting
    # ----------------------------------------------------------------
    log.info("=== Step 3: Generating report ===")
    df = pd.read_csv(RESULTS_CSV)

    # Normalise empty values
    df["software"] = df["software"].fillna("Unknown / Custom")
    df["category"] = df["category"].fillna("Unknown / Custom")
    df["province"] = df["province"].str.upper().str.strip()

    generate_html(df, REPORT_HTML)
    log.info("Report → %s", REPORT_HTML)
    log.info("Done. %d clubs processed.", len(df))

    # Print summary table to console
    summary = df["software"].value_counts().reset_index()
    summary.columns = ["Software", "Clubs"]
    print("\n=== Software distribution ===")
    print(summary.to_string(index=False))


# -------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canadian swim-club software survey")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process only the first N clubs (useful for testing)"
    )
    parser.add_argument(
        "--no-cache", action="store_true",
        help="Ignore cached results.csv and re-scan everything"
    )
    parser.add_argument(
        "--delay", type=float, default=0.0,
        help="Extra delay in seconds between requests (on top of built-in politeness delay)"
    )
    args = parser.parse_args()

    run(
        limit=args.limit,
        use_cache=not args.no_cache,
        extra_delay=args.delay,
    )
