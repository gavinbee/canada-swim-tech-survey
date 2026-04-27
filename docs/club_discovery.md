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
| Data format | Club contacts are published as individual PDF downloads (one per club). No structured name/website data in the HTML. |
| Status | ❌ Not implemented — data is only in PDFs |

---

### Yukon, Northwest Territories, Nunavut

Not linked from findaclub.swimming.ca. Any affiliated clubs appear in the
national Swimming Canada feed.

---

## Adding a new provincial scraper

1. Check `_PROVINCIAL_SOURCES` in `src/clubs.py` — if the province is missing, add it.
2. Fetch the club directory page with Python `requests` and inspect for structure:
   - Static HTML table → add a `html_table_XX` scraper type + `_parse_XX_table()` function
   - Gatsby site → try `<page-url>/page-data/<path>/page-data.json`; if it has `result.data.wagtail.page.children`, use `gatsby_json`
   - WordPress with custom blocks → inspect `div` class names and text patterns
   - Squarespace → try `?format=json`; inspect `collection.items`
   - Dynamic / headless-only → note it as not implemented in `docs/club_discovery.md`
3. Implement a `_parse_XX_YYY(province, response)` function that returns a list of
   dicts with keys: `name`, `province`, `province_name`, `website`, `source`.
   Use `_make_club(name, website, province, postal)` as a helper.
4. Register the new entry in `_PROVINCIAL_SOURCES` as `("XX", "scraper_type", url)`.
5. Run `python main.py --refresh-clubs` locally to refresh `data/clubs.json`.
6. Update this document and [data_sources.md](data_sources.md).
