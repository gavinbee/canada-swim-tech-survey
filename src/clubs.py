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

import requests

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
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


def fetch_all_clubs():
    """
    Fetch 400+ clubs from Swimming Canada's club-list API.
    Returns a list of dicts ready for software detection.
    """
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
        log.error("Failed to fetch club list: %s", exc)
        return []

    # Response is JSONP: load_clubs([...])
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
        log.error("JSON parse error: %s", exc)
        return []

    clubs = []
    seen = set()
    for item in raw:
        name = item.get("name", "").strip()
        address = item.get("address", "")
        website = (item.get("website") or "").strip().rstrip("/")
        province = _province_from_address(address)
        city = _city_from_address(address)

        # Skip Facebook pages as the "website" — flag them specially
        if "facebook.com" in website:
            website_clean = ""
            facebook_page = website
        else:
            website_clean = website
            facebook_page = ""

        # Deduplicate on (name, website)
        key = (name.lower(), website_clean.lower())
        if key in seen:
            continue
        seen.add(key)

        clubs.append({
            "name": name,
            "province": province,
            "province_name": PROVINCE_NAMES.get(province, province),
            "city": city,
            "website": website_clean,
            "facebook": facebook_page,
            "members": None,
            "lat": item.get("lat"),
            "lng": item.get("lng"),
            "source": "swimming_canada_api",
        })

    log.info("Fetched %d clubs (%d with websites)", len(clubs),
             sum(1 for c in clubs if c["website"]))
    return clubs
