"""
Club name typo detection and resolution.

When a provincial scraper produces a club name containing a word that looks
like a misspelling of a common swim-club word (e.g. "Clun" instead of "Club"),
this module flags it.  The resolution for that name is looked up in
data/name_resolutions.json.

Resolution file
---------------
data/name_resolutions.json is committed to the repository so that all runs
(local and CI) apply saved decisions without human input.  Each key is the
original scraped name; each value is one of:

    {"action": "rename", "to": "Corrected Name"}
    {"action": "keep"}   # name is intentional, not a typo
    {"action": "skip"}   # entry is not a real club, omit it

When a suspect name has no saved resolution
-------------------------------------------
The club is skipped and its full scraped record is written to
data/clubs_suspects.json.  fetch_all_clubs then raises UnresolvedSuspectError
so the run fails with exit code 2.

To resolve: add entries to data/name_resolutions.json (edit manually or commit
the file after a colleague reviews it), then either:
  - re-run --refresh-clubs to re-scrape and apply all resolutions, or
  - run --apply-suspects to merge the already-scraped records from
    data/clubs_suspects.json without re-scraping.

Vocabulary design
-----------------
_CLUB_VOCAB contains only words that are unambiguously standard English or
French swim-club words.  Words fewer than 4 characters are never checked to
avoid false positives on short prepositions ("de", "les", …).  French forms
("aquatique", "natation") are listed as exact-match entries so they pass
through without triggering, rather than appearing similar to their English
counterparts.
"""

import difflib
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

_CLUB_VOCAB = {
    # English
    "club", "swim", "swimming", "aquatic", "aquatics",
    # French (listed so they match exactly and are never flagged as typos)
    "natation", "aquatique", "aquatiques",
}

# ---------------------------------------------------------------------------
# Resolution file
# ---------------------------------------------------------------------------

NAME_RESOLUTIONS_PATH = Path(__file__).parent.parent / "data" / "name_resolutions.json"


class UnresolvedSuspectError(Exception):
    """Raised by fetch_all_clubs when suspect names have no saved resolution."""
    def __init__(self, names: list[str]):
        self.names = names
        super().__init__(f"Unresolved suspected typos: {names}")


def _load_resolutions() -> dict:
    if NAME_RESOLUTIONS_PATH.exists():
        with open(NAME_RESOLUTIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _find_suspects(name: str) -> list[tuple[str, str]]:
    """Return (word, suggestion) pairs for words that look like typos of vocab words."""
    suspects = []
    for word in name.split():
        w = word.lower().strip(".,-()")
        if len(w) < 4 or w in _CLUB_VOCAB:
            continue
        matches = difflib.get_close_matches(w, _CLUB_VOCAB, n=1, cutoff=0.75)
        if matches:
            suspects.append((word, matches[0].title()))
    return suspects

# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _resolve_name(name: str, unresolved: list[str]) -> tuple[str, bool]:
    """
    Check name for likely typos and apply any saved resolution.

    Returns (resolved_name, skip).  On skip the caller must not add the club
    to the output list.  If no resolution is saved, appends to unresolved and
    skips; fetch_all_clubs raises UnresolvedSuspectError after all clubs are
    parsed so the run fails visibly.
    """
    suspects = _find_suspects(name)
    if not suspects:
        return name, False

    resolutions = _load_resolutions()
    if name in resolutions:
        entry = resolutions[name]
        action = entry.get("action")
        if action == "rename":
            log.info("Renaming %r → %r (from name_resolutions.json)", name, entry["to"])
            return entry["to"], False
        if action == "keep":
            return name, False
        if action == "skip":
            log.info("Skipping %r (from name_resolutions.json)", name)
            return name, True

    log.warning(
        "Unresolved suspected typo in club name %r — skipping. "
        "Add a resolution to data/name_resolutions.json, then re-run "
        "--refresh-clubs or run --apply-suspects.",
        name,
    )
    unresolved.append(name)
    return name, True
