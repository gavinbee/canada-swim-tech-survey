"""
Club name typo detection and interactive resolution.

When a provincial scraper produces a club name that contains a word that looks
like a misspelling of a common swim-club word (e.g. "Clun" instead of "Club"),
this module flags it and applies whichever resolution has been saved for that
name in data/name_resolutions.json.

Resolution file
---------------
data/name_resolutions.json is committed to the repository so that CI runs can
apply saved decisions without human input.  Each key is the original scraped
name; each value is one of:

    {"action": "rename", "to": "Corrected Name"}
    {"action": "keep"}   # name is intentional, not a typo
    {"action": "skip"}   # entry is not a real club, omit it

Interactive runs (--refresh-clubs in a terminal)
------------------------------------------------
When a suspect name has no saved resolution the operator is prompted:
  (k) keep as-is — saves {"action": "keep"} and continues
  (c) correct    — prompts for the corrected name, saves {"action": "rename", …}
  (s) skip       — saves {"action": "skip"} and omits the club
The choice is written to the file immediately so partial progress survives if
the process is interrupted.

Non-interactive runs (e.g. GitHub Actions)
------------------------------------------
If a suspect name has no saved resolution the club is skipped, the name is
appended to the `unresolved` list passed in by the caller, and
fetch_all_clubs raises UnresolvedSuspectError so the workflow fails with
exit code 2.  The operator then runs --refresh-clubs locally, resolves the
names interactively, and commits both data/name_resolutions.json and the
updated data/clubs.json.

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
import sys
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
    """Raised by fetch_all_clubs when unresolved name suspects are found non-interactively."""
    def __init__(self, names: list[str]):
        self.names = names
        super().__init__(f"Unresolved suspected typos: {names}")


def _load_resolutions() -> dict:
    if NAME_RESOLUTIONS_PATH.exists():
        with open(NAME_RESOLUTIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_resolutions(resolutions: dict) -> None:
    NAME_RESOLUTIONS_PATH.parent.mkdir(exist_ok=True)
    with open(NAME_RESOLUTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(resolutions, f, indent=2, ensure_ascii=False, sort_keys=True)

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


def _prompt_resolution(name: str, suspects: list[tuple[str, str]]) -> tuple[str, bool]:
    """Prompt the user interactively and persist their choice. Returns (name, skip)."""
    resolutions = _load_resolutions()
    print(f"\nSuspected typo in club name: {name!r}")
    for word, suggestion in suspects:
        print(f"  '{word}' resembles '{suggestion}'")
    print("Options: (k) keep as-is  (c) correct  (s) skip club")
    while True:
        choice = input("Choice [k/c/s]: ").strip().lower()
        if choice == "k":
            resolutions[name] = {"action": "keep"}
            _save_resolutions(resolutions)
            return name, False
        if choice == "c":
            corrected = input(f"Corrected name [{name}]: ").strip() or name
            resolutions[name] = {"action": "rename", "to": corrected}
            _save_resolutions(resolutions)
            return corrected, False
        if choice == "s":
            resolutions[name] = {"action": "skip"}
            _save_resolutions(resolutions)
            return name, True
        print("Please enter k, c, or s.")


def _resolve_name(name: str, unresolved: list[str]) -> tuple[str, bool]:
    """
    Check name for likely typos and apply any saved resolution.

    Returns (resolved_name, skip).  On skip the caller must not add the club
    to the output list.  Appends to unresolved when a suspect has no saved
    resolution in a non-interactive run; fetch_all_clubs raises
    UnresolvedSuspectError if that list is non-empty after all clubs are parsed.
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

    if sys.stdin.isatty():
        return _prompt_resolution(name, suspects)

    log.error(
        "Unresolved suspected typo in club name %r — skipping. "
        "Run --refresh-clubs locally to resolve and commit name_resolutions.json.",
        name,
    )
    unresolved.append(name)
    return name, True
