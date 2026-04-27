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
import warnings
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

# Provincial sources: (province_code, scraper_type, url)
# scraper_type: "gatsby_json" | "html_table_bc" | "html_table_mb" | "html_divs_ab"
_PROVINCIAL_SOURCES = [
    ("ON", "gatsby_json",  "https://www.swimontario.com/page-data/clubs/find-a-club/page-data.json"),
    ("BC", "html_table_bc", "https://swimbc.ca/clubs/how-to-join-a-swim-club/"),
    ("AB", "html_divs_ab",  "https://swimalberta.ca/community/clubs/find-a-club/"),
    ("MB", "html_table_mb", "https://swimmanitoba.mb.ca/clubs/"),
]


def fetch_all_clubs(force_refresh=False):
    """
    Return Canadian swim club dicts ready for software detection.

    Tries the live Swimming Canada API first.  If that fails (e.g. the
    server blocks cloud IP ranges such as GitHub Actions), falls back to
    the committed snapshot at data/clubs.json.

    Supplements the Swimming Canada list with provincial association
    directories to catch clubs not registered nationally.

    Pass force_refresh=True (or run main.py --refresh-clubs) to skip the
    snapshot and always hit the live APIs, then save a new snapshot.
    """
    if not force_refresh and SNAPSHOT_PATH.exists():
        return _load_snapshot()

    clubs = _fetch_live()
    if clubs:
        clubs = _merge_provincial(clubs)
        _save_snapshot(clubs)
        return clubs

    # Live fetch failed — fall back to snapshot
    if SNAPSHOT_PATH.exists():
        log.warning("Live fetch failed; using committed snapshot %s", SNAPSHOT_PATH)
        return _load_snapshot()

    return []


def _normalise_website(url):
    if not url:
        return ""
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    if "facebook.com" in url:
        return ""
    return url


def _merge_provincial(clubs):
    """Fetch each known provincial directory and add clubs missing from the national list."""
    existing_names = {c["name"].lower() for c in clubs}
    existing_sites = {c["website"].lower() for c in clubs if c["website"]}

    added = 0
    for province, scraper, url in _PROVINCIAL_SOURCES:
        provincial = _fetch_provincial(province, scraper, url)
        for club in provincial:
            name_key = club["name"].lower()
            site_key = club["website"].lower() if club["website"] else None
            if name_key in existing_names:
                continue
            if site_key and site_key in existing_sites:
                continue
            clubs.append(club)
            existing_names.add(name_key)
            if site_key:
                existing_sites.add(site_key)
            added += 1

    if added:
        log.info("Added %d clubs from provincial directories", added)
    return clubs


def _fetch_provincial(province, scraper, url):
    log.info("Fetching provincial club list (%s): %s", province, url)
    ua = {"User-Agent": HEADERS["User-Agent"]}
    try:
        r = requests.get(url, headers=ua, timeout=20, verify=False)
        r.raise_for_status()
    except Exception as exc:
        log.warning("Provincial fetch failed (%s): %s", province, exc)
        return []

    if scraper == "gatsby_json":
        return _parse_gatsby_json(province, r)
    if scraper == "html_table_bc":
        return _parse_bc_table(province, r)
    if scraper == "html_table_mb":
        return _parse_mb_table(province, r)
    if scraper == "html_divs_ab":
        return _parse_ab_divs(province, r)

    log.warning("Unknown provincial scraper type: %s", scraper)
    return []


def _make_club(name, website, province, postal=""):
    prov = _province_from_address(postal) or province
    return {
        "name": name,
        "province": prov,
        "province_name": PROVINCE_NAMES.get(prov, prov),
        "website": _normalise_website(website),
        "source": f"provincial_{province.lower()}",
    }


def _parse_gatsby_json(province, r):
    try:
        data = r.json()
        children = data["result"]["data"]["wagtail"]["page"]["children"]
    except (ValueError, KeyError, TypeError) as exc:
        log.warning("Gatsby JSON parse failed (%s): %s", province, exc)
        return []
    clubs = []
    for item in children:
        name = (item.get("name") or "").strip()
        if name:
            clubs.append(_make_club(name, item.get("website") or "", province,
                                    item.get("postalcode") or ""))
    log.info("Fetched %d clubs from Gatsby JSON (%s)", len(clubs), province)
    return clubs


def _parse_bc_table(province, r):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table")
    if not table:
        log.warning("BC table not found")
        return []
    clubs = []
    for row in table.find_all("tr")[1:]:  # skip header
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        name = cells[1].get_text(strip=True)
        links = [a["href"] for a in row.find_all("a", href=True)
                 if a["href"].startswith("http") and "google" not in a["href"]
                 and "facebook" not in a["href"]]
        if name:
            clubs.append(_make_club(name, links[0] if links else "", province))
    log.info("Fetched %d clubs from BC table", len(clubs))
    return clubs


def _parse_mb_table(province, r):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "lxml")
    table = soup.find("table")
    if not table:
        log.warning("MB table not found")
        return []
    clubs = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        name = cells[0].get_text(strip=True)
        links = [a["href"] for a in row.find_all("a", href=True)
                 if a["href"].startswith("http") and "google" not in a["href"]
                 and "facebook" not in a["href"]]
        if name:
            clubs.append(_make_club(name, links[0] if links else "", province))
    log.info("Fetched %d clubs from MB table", len(clubs))
    return clubs


def _parse_ab_divs(province, r):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "lxml")
    clubs = []
    for div in soup.find_all("div", class_="club_directory_col"):
        text = div.get_text(separator="|", strip=True)
        m = re.search(r"Club Name:\|([^|]+)", text)
        name = m.group(1).strip() if m else ""
        links = [a["href"] for a in div.find_all("a", href=True)
                 if a["href"].startswith("http") and "google" not in a["href"]
                 and "facebook" not in a["href"] and "swimalberta" not in a["href"]]
        if name:
            clubs.append(_make_club(name, links[0] if links else "", province))
    log.info("Fetched %d clubs from AB divs", len(clubs))
    return clubs


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
        website_clean = _normalise_website(item.get("website") or "")
        province = _province_from_address(address)

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
