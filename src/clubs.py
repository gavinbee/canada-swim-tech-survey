"""
Club discovery: fetches Canadian swim clubs from Swimming Canada's
club-list API at swimming.ca/club-list.php (returns JSONP).

Derives province from the postal code in each club's address field.
Returns a list of dicts: name, province, province_name, city, website, members, source.
"""

import json
import logging
import re
import time
from pathlib import Path

import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    # club-list.php is loaded by JS on findaclub.swimming.ca — the server
    # checks Referer to block direct non-browser requests
    "Referer": "https://findaclub.swimming.ca/",
    "Accept": "text/javascript, application/javascript, */*",
    "Accept-Language": "en-CA,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}

CLUB_LIST_URL = "https://www.swimming.ca/club-list.php"

# First letter of Canadian postal code → province code
_POSTAL_TO_PROV = {
    "A": "NL",
    "B": "NS",
    "C": "PE",
    "E": "NB",
    "G": "QC",
    "H": "QC",
    "J": "QC",
    "K": "ON",
    "L": "ON",
    "M": "ON",
    "N": "ON",
    "P": "ON",
    "R": "MB",
    "S": "SK",
    "T": "AB",
    "V": "BC",
    "X": "NT",
    "Y": "YT",
}

PROVINCE_NAMES = {
    "BC": "British Columbia",
    "AB": "Alberta",
    "SK": "Saskatchewan",
    "MB": "Manitoba",
    "ON": "Ontario",
    "QC": "Quebec",
    "NB": "New Brunswick",
    "NS": "Nova Scotia",
    "PE": "Prince Edward Island",
    "NL": "Newfoundland and Labrador",
    "YT": "Yukon",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
}

_POSTAL_RE = re.compile(r"([A-Z])\d[A-Z]\s*\d[A-Z]\d", re.I)
_CITY_RE = re.compile(r"^(.+?)\s+[A-Z]\d[A-Z]\s*\d[A-Z]\d", re.I)


def _province_from_address(address):
    m = _POSTAL_RE.search(address)
    if m:
        return _POSTAL_TO_PROV.get(m.group(1).upper(), "")
    return ""


def _city_from_address(address):
    m = _CITY_RE.search(address)
    if m:
        return m.group(1).strip()
    return ""


SNAPSHOT_PATH = Path(__file__).parent.parent / "data" / "clubs.json"


def fetch_all_clubs(force_refresh=False):
    """
    Return 400+ Canadian swim club dicts ready for software detection.

    Tries the live Swimming Canada API first.  If that fails (e.g. the
    server blocks cloud IP ranges such as GitHub Actions), falls back to
    the committed snapshot at data/clubs.json.

    Pass force_refresh=True (or run main.py --refresh-clubs) to skip the
    snapshot and always hit the live API, then save a new snapshot.
    """
    if not force_refresh and SNAPSHOT_PATH.exists():
        return _load_snapshot()

    clubs = _fetch_live()
    if clubs:
        _save_snapshot(clubs)
        return clubs

    # Live fetch failed — fall back to snapshot
    if SNAPSHOT_PATH.exists():
        log.warning("Live fetch failed; using committed snapshot %s", SNAPSHOT_PATH)
        return _load_snapshot()

    return []


def _fetch_live():
    log.info("Fetching club list from %s", CLUB_LIST_URL)
    try:
        r = requests.get(
            CLUB_LIST_URL,
            headers=HEADERS,
            timeout=20,
            params={"preview": "true"},
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Live club-list fetch failed: %s", exc)
        return []

    text = r.text.strip()
    if text.startswith("load_clubs("):
        text = text[len("load_clubs("):]
        if text.endswith(")"):
            text = text[:-1]
    elif text.startswith("("):
        text = text[1:-1]

    try:
        raw = json.loads(text)
    except ValueError as exc:
        log.warning("JSON parse error: %s", exc)
        return []

    clubs = []
    seen = set()
    for item in raw:
        name = item.get("name", "").strip()
        address = item.get("address", "")
        website = (item.get("website") or "").strip().rstrip("/")
        province = _province_from_address(address)

        if "facebook.com" in website:
            website_clean = ""
        else:
            website_clean = website

        key = (name.lower(), website_clean.lower())
        if key in seen:
            continue
        seen.add(key)

        clubs.append({
            "name": name,
            "province": province,
            "province_name": PROVINCE_NAMES.get(province, province),
            "website": website_clean,
            "source": "swimming_canada_api",
        })

    log.info("Fetched %d clubs live (%d with websites)", len(clubs),
             sum(1 for c in clubs if c["website"]))
    return clubs


def _load_snapshot():
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        clubs = json.load(f)
    log.info("Loaded %d clubs from snapshot %s", len(clubs), SNAPSHOT_PATH)
    return clubs


def _save_snapshot(clubs):
    SNAPSHOT_PATH.parent.mkdir(exist_ok=True)
    snapshot = [
        {"name": c["name"], "province": c["province"],
         "province_name": c["province_name"], "website": c["website"]}
        for c in clubs
    ]
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    log.info("Saved club snapshot → %s", SNAPSHOT_PATH)
