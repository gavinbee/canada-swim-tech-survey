"""Tests for src/name_resolution.py — club name typo detection and resolution."""

import json
from unittest.mock import MagicMock

from src.name_resolution import _find_suspects, _resolve_name


class TestFindSuspects:
    def test_obvious_typo_detected(self):
        assert _find_suspects("Aqua Aces Swim Clun") == [("Clun", "Club")]

    def test_correct_name_no_suspects(self):
        assert _find_suspects("Corner Brook Rapids Swim Club") == []

    def test_short_words_ignored(self):
        # "de", "les" etc. must not be checked against vocab
        assert _find_suspects("Club de Natation") == []

    def test_french_aquatique_not_flagged(self):
        # "aquatique" is in _CLUB_VOCAB as an accepted French form
        assert _find_suspects("Club Aquatique de Montréal") == []

    def test_unrelated_word_not_flagged(self):
        assert _find_suspects("Poseidon Swim Club") == []


class TestResolveName:
    def test_clean_name_passes_through(self):
        unresolved = []
        name, skip = _resolve_name("Vancouver Swim Club", unresolved)
        assert name == "Vancouver Swim Club"
        assert skip is False
        assert unresolved == []

    def test_rename_resolution_applied(self, tmp_path, monkeypatch):
        resolutions = {"Aqua Aces Swim Clun": {"action": "rename", "to": "Aqua Aces Swim Club"}}
        res_file = tmp_path / "name_resolutions.json"
        res_file.write_text(json.dumps(resolutions), encoding="utf-8")
        monkeypatch.setattr("src.name_resolution.NAME_RESOLUTIONS_PATH", res_file)
        unresolved = []
        name, skip = _resolve_name("Aqua Aces Swim Clun", unresolved)
        assert name == "Aqua Aces Swim Club"
        assert skip is False
        assert unresolved == []

    def test_skip_resolution_applied(self, tmp_path, monkeypatch):
        resolutions = {"Aqua Aces Swim Clun": {"action": "skip"}}
        res_file = tmp_path / "name_resolutions.json"
        res_file.write_text(json.dumps(resolutions), encoding="utf-8")
        monkeypatch.setattr("src.name_resolution.NAME_RESOLUTIONS_PATH", res_file)
        unresolved = []
        name, skip = _resolve_name("Aqua Aces Swim Clun", unresolved)
        assert skip is True
        assert unresolved == []  # file-driven skip, not an unresolved suspect

    def test_keep_resolution_applied(self, tmp_path, monkeypatch):
        resolutions = {"Odd But Valid Name Clun": {"action": "keep"}}
        res_file = tmp_path / "name_resolutions.json"
        res_file.write_text(json.dumps(resolutions), encoding="utf-8")
        monkeypatch.setattr("src.name_resolution.NAME_RESOLUTIONS_PATH", res_file)
        unresolved = []
        name, skip = _resolve_name("Odd But Valid Name Clun", unresolved)
        assert name == "Odd But Valid Name Clun"
        assert skip is False
        assert unresolved == []

    def test_unresolved_non_interactive_skips_and_appends(self, tmp_path, monkeypatch):
        """Non-interactive run with no resolution must skip the club and append to unresolved."""
        res_file = tmp_path / "name_resolutions.json"
        res_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("src.name_resolution.NAME_RESOLUTIONS_PATH", res_file)
        monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: False))
        unresolved = []
        name, skip = _resolve_name("Aqua Aces Swim Clun", unresolved)
        assert skip is True
        assert "Aqua Aces Swim Clun" in unresolved
