# Club Discovery — Source Inventory

All provincial association home pages are linked from
[findaclub.swimming.ca](https://findaclub.swimming.ca/).

## National source

| Source | URL | Format | Status |
|---|---|---|---|
| Swimming Canada club-list API | `https://www.swimming.ca/club-list.php` | JSONP (`load_clubs([…])`) — fetched with `Referer: https://findaclub.swimming.ca/` and `X-Requested-With: XMLHttpRequest` | ✅ Implemented (`swimming_canada_api`) |

The national feed is the primary source. Provincial directories are merged
afterwards and deduplicated on (name, website).

Because the Swimming Canada API blocks GitHub Actions IP ranges, the merged
list is committed to `data/clubs.json` as a snapshot and loaded by default.
Run `python main.py --refresh-clubs` locally to re-fetch and update the snapshot.

---

## Provincial sources

### British Columbia — Swim BC

| Field | Value |
|---|---|
| Association site | https://swimbc.ca/ |
| Club directory | https://swimbc.ca/clubs/how-to-join-a-swim-club/ |
| Data format | Static HTML `<table>` — columns: Club Code, Club, Region, Website |
| Website field | `<a href="…">` in the last column; some rows have no link |
| Scraper type | `html_table_bc` |
| Status | ✅ Implemented |

---

### Alberta — Swim Alberta

| Field | Value |
|---|---|
| Association site | https://swimalberta.ca/ (redirects from http://www.swimalberta.ca/ — SSL cert mismatch on `www`, fetch with `verify=False`) |
| Club directory | https://swimalberta.ca/community/clubs/find-a-club/ |
| Data format | WordPress page using Isotope.js for client-side filtering. All club blocks are present in the static HTML as `<div class="club_directory_col">` elements. Each block contains pipe-separated text including `Club Name:\|<name>` and an `<a href="…">` for the website. |
| Scraper type | `html_divs_ab` — finds all `div.club_directory_col`, regex-extracts name, finds first non-Google/non-Facebook href |
| Status | ✅ Implemented |

---

### Saskatchewan — Swim Sask

| Field | Value |
|---|---|
| Association site | https://www.swimsask.ca/ |
| Club directory | https://www.swimsask.ca/join-a-club |
| Data format | Squarespace site. The `?format=json` endpoint returns a `collection` object with zero `items`. The page body contains only membership benefits text — no club names or websites in static HTML. |
| Status | ❌ Not implemented — no structured data accessible without a headless browser |

---

### Manitoba — Swim Manitoba

| Field | Value |
|---|---|
| Association site | https://swimmanitoba.mb.ca/ |
| Club directory | https://swimmanitoba.mb.ca/clubs/ |
| Data format | WordPress site with a static HTML `<table>` — columns: Club, Address, Services, Website. The Website column contains an `<a href="…">` for clubs that have one; some rows have no link or only a Facebook link. |
| Scraper type | `html_table_mb` |
| Status | ✅ Implemented |

---

### Ontario — Swim Ontario

| Field | Value |
|---|---|
| Association site | https://www.swimontario.com/ |
| Club directory | https://www.swimontario.com/clubs/find-a-club/ |
| Data format | Gatsby site. Club list is loaded dynamically from `https://admin.swimontario.com/itemsearch/` at runtime, but the full club data is also baked into the Gatsby page-data JSON at `https://www.swimontario.com/page-data/clubs/find-a-club/page-data.json` under `result.data.wagtail.page.children`. Each child has: `name`, `website`, `postalcode`, `city`, `region`, `email`, etc. |
| Scraper type | `gatsby_json` |
| Status | ✅ Implemented |

---

### Quebec — Natation Québec

| Field | Value |
|---|---|
| Association site | https://www.swimming.ca/fr/ (Swimming Canada FR) |
| Club directory | https://trouverunclub.natation.ca/ |
| Data format | Same JSONP feed as the national Swimming Canada API (`swimming.ca/club-list.php`) — QC clubs are already included in the national data. |
| Status | ✅ Covered by national feed — no separate scraper needed |

---

### New Brunswick — Swimming NB / Natation NB

| Field | Value |
|---|---|
| Association site | https://www.swimnb.ca/ |
| Club directory | https://www.swimnb.ca/menu/find-a-club-trouver-un-club |
| Data format | Static HTML page lists city names only (Bathurst, Campbellton, Caraquet, …) with no club names or website links visible. Likely rendered by a CMS with data loaded client-side. |
| Status | ❌ Not implemented — no structured data accessible without a headless browser |

---

### Nova Scotia — Swim Nova Scotia

| Field | Value |
|---|---|
| Association site | https://www.swimnovascotia.com/ |
| Club directory | https://www.swimnovascotia.com/clubs |
| Data format | Squarespace site. No tables or club-specific links in static HTML; club data appears to be loaded dynamically. |
| Status | ❌ Not implemented — no structured data accessible without a headless browser |

---

### Prince Edward Island — Swim PEI

| Field | Value |
|---|---|
| Association site | https://swimpei.com/ |
| Club directory | https://swimpei.com/clubs/ |
| Data format | WordPress site. The clubs page contains only affiliation/registration information text — no club listing with names and websites. |
| Status | ❌ Not implemented — no club list found on the page |

---

### Newfoundland and Labrador — Swimming NL

| Field | Value |
|---|---|
| Association site | https://swimmingnl.ca/ |
| Club directory | https://swimmingnl.ca/directory |
| Data format | GoDaddy Website Builder page. Each club is listed as a PDF download link; the anchor text contains the club name followed by a year suffix and "(pdf)Download" (e.g. "Aqua Aces Swim Club 2025-26(pdf)Download"). Each PDF is a structured contact form with fields including "Club Website" (value may be "N/A"). The scraper strips the trailing suffix from each anchor, skips the "Swimming NL Executive" admin entry, fetches each PDF, and extracts the "Club Website" value via regex. Requires `pdfplumber`. |
| Scraper type | `html_pdf_links_nl` |
| Status | ✅ Implemented |

---

### Yukon, Northwest Territories, Nunavut

Not linked from findaclub.swimming.ca. Any affiliated clubs appear in the
national Swimming Canada feed.

---

## Club name typo detection and resolution (`src/name_resolution.py`)

When a provincial scraper produces a club name containing a word that looks like
a misspelling of a common swim-club term (e.g. "Clun" instead of "Club"), the
name is flagged as a suspected typo. The resolution is looked up in
`data/name_resolutions.json` (committed to the repo). If no resolution is saved,
behaviour depends on whether the run is interactive or not.

### Resolution file — `data/name_resolutions.json`

Each key is the original scraped name; each value is one of:

```json
{ "action": "rename", "to": "Corrected Name" }
{ "action": "keep" }
{ "action": "skip" }
```

### Interactive runs (`--refresh-clubs` in a terminal)

When a suspect name has no saved resolution the operator is prompted:
- **(k) keep** — saves `{"action": "keep"}` and continues
- **(c) correct** — prompts for the corrected name, saves `{"action": "rename", …}`
- **(s) skip** — saves `{"action": "skip"}` and omits the club

The choice is written to the file immediately so partial progress survives interruptions.

### Non-interactive runs (e.g. GitHub Actions)

If a suspect name has no saved resolution, the club is skipped and the name is
collected. After all clubs are parsed, `fetch_all_clubs` raises
`UnresolvedSuspectError`, which causes `main.py` to exit with code 2, failing
the workflow. To resolve: run `--refresh-clubs` locally (interactive terminal),
then commit both `data/name_resolutions.json` and the updated `data/clubs.json`.

### Vocabulary design

`_CLUB_VOCAB` contains only words that are unambiguously standard English or
French swim-club terms. Words fewer than 4 characters are never checked to avoid
false positives on short prepositions ("de", "les", …). French forms
("aquatique", "natation") are listed as exact-match entries so they pass through
without triggering.

---

## Adding a new provincial scraper

1. Check `_PROVINCIAL_SOURCES` in `src/clubs.py` — if the province is missing, add it.
2. Fetch the club directory page with Python `requests` and inspect for structure:
   - Static HTML table → add a `html_table_XX` scraper type + `_parse_XX_table()` function
   - Gatsby site → try `<page-url>/page-data/<path>/page-data.json`; if it has `result.data.wagtail.page.children`, use `gatsby_json`
   - WordPress with custom blocks → inspect `div` class names and text patterns
   - Squarespace → try `?format=json`; inspect `collection.items`
   - Dynamic / headless-only → note it as not implemented in `docs/club_discovery.md`
3. Implement a `_parse_XX_YYY(province, response, source_url="", unresolved=None)` function
   that returns a list of dicts. Use
   `_make_club(name, website, province, postal="", source_url=source_url, unresolved=unresolved)`
   as a helper — it handles name-typo resolution, sets `province`, `province_name`,
   `website` (normalised), and `source_url`. It returns `None` for skipped clubs, so always
   guard with `if club:`.
4. Register the new entry in `_PROVINCIAL_SOURCES` as `("XX", "scraper_type", url)`.
   `_fetch_provincial` dispatches on the scraper type string and passes `url` as `source_url`.
5. Add a short label for the new source in `_SOURCE_LABELS` in `src/visualize.py` so the
   HTML report table shows a linked label (e.g. "Swim XX") instead of the raw URL.
6. Run `python main.py --refresh-clubs` locally to refresh `data/clubs.json`.
7. Update this document and [data_sources.md](data_sources.md).
8. Write tests for the new parser in `tests/test_clubs.py`.
