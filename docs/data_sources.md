# Data Sources

The club list is assembled from the following publicly accessible directories.
The national feed is the primary source; provincial directories are merged
afterwards and deduplicated on (name, website).

| Source | URL | Scope |
|---|---|---|
| Swimming Canada club-list API | https://www.swimming.ca | National (all provinces) |
| Swim BC | https://swimbc.ca | British Columbia |
| Swim Alberta | https://swimalberta.ca | Alberta |
| Swim Manitoba | https://swimmanitoba.mb.ca | Manitoba |
| Swim Ontario | https://www.swimontario.com | Ontario |
| Swimming NL | https://swimmingnl.ca/directory | Newfoundland and Labrador |

For implementation details — scraper types, data formats, and provinces not
yet covered — see [club_discovery.md](club_discovery.md).
