"""Tests for src/clubs.py — club discovery and address parsing."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.clubs import (
    _city_from_address,
    _province_from_address,
    fetch_all_clubs,
)


class TestProvinceFromAddress:
    def test_bc(self):
        assert _province_from_address("123 Main St V5K 0A1") == "BC"

    def test_ontario(self):
        assert _province_from_address("45 King St M5V 2T6") == "ON"

    def test_quebec(self):
        assert _province_from_address("12 Rue des Érables H2X 1Y4") == "QC"

    def test_alberta(self):
        assert _province_from_address("99 Jasper Ave T5J 1W2") == "AB"

    def test_nova_scotia(self):
        assert _province_from_address("1 Spring Garden Rd B3J 3R4") == "NS"

    def test_pei(self):
        assert _province_from_address("40 Enman Cres C1E 1E6") == "PE"

    def test_new_brunswick(self):
        assert _province_from_address("100 Brunswick St E3B 1G8") == "NB"

    def test_newfoundland(self):
        assert _province_from_address("10 Water St A1C 1A5") == "NL"

    def test_manitoba(self):
        assert _province_from_address("300 Main St R3C 1B8") == "MB"

    def test_saskatchewan(self):
        assert _province_from_address("2220 College Ave S4P 1C4") == "SK"

    def test_yukon(self):
        assert _province_from_address("100 Main St Y1A 2B5") == "YT"

    def test_northwest_territories(self):
        assert _province_from_address("5020 48 St X1A 2N6") == "NT"

    def test_no_postal_code(self):
        assert _province_from_address("123 Unknown Street") == ""

    def test_empty(self):
        assert _province_from_address("") == ""

    def test_lowercase_postal(self):
        assert _province_from_address("123 main st m5v 2t6") == "ON"


class TestCityFromAddress:
    def test_single_word_city(self):
        assert _city_from_address("Vancouver V5K 0A1") == "Vancouver"

    def test_multi_word_city(self):
        assert _city_from_address("St. John's A1C 1A5") == "St. John's"

    def test_with_street(self):
        assert _city_from_address("100 Main St Toronto M5V 2T6") == "100 Main St Toronto"

    def test_no_postal_code(self):
        assert _city_from_address("No postal code here") == ""

    def test_empty(self):
        assert _city_from_address("") == ""


class TestFetchAllClubs:
    _SAMPLE_CLUBS = [
        {
            "name": "Test Swim Club",
            "address": "100 Main St M5V 2T6",
            "website": "https://testswimclub.ca",
            "phone": "",
            "lat": "43.6",
            "lng": "-79.4",
            "category": "",
            "type": "",
        },
        {
            "name": "Facebook Club",
            "address": "200 Oak Ave V5K 0A1",
            "website": "https://www.facebook.com/facebookclub",
            "phone": "",
            "lat": "49.2",
            "lng": "-123.1",
            "category": "",
            "type": "",
        },
        {
            "name": "No Website Club",
            "address": "300 Elm St H2X 1Y4",
            "website": "",
            "phone": "",
            "lat": "45.5",
            "lng": "-73.6",
            "category": "",
            "type": "",
        },
    ]

    def _make_response(self, clubs):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.text = "load_clubs(" + json.dumps(clubs) + ")"
        return mock

    @patch("src.clubs.requests.get")
    def test_basic_fetch(self, mock_get):
        mock_get.return_value = self._make_response(self._SAMPLE_CLUBS)
        clubs = fetch_all_clubs()
        assert len(clubs) == 3

    @patch("src.clubs.requests.get")
    def test_province_derived_from_postal(self, mock_get):
        mock_get.return_value = self._make_response(self._SAMPLE_CLUBS)
        clubs = fetch_all_clubs()
        by_name = {c["name"]: c for c in clubs}
        assert by_name["Test Swim Club"]["province"] == "ON"
        assert by_name["Facebook Club"]["province"] == "BC"
        assert by_name["No Website Club"]["province"] == "QC"

    @patch("src.clubs.requests.get")
    def test_facebook_url_cleared(self, mock_get):
        mock_get.return_value = self._make_response(self._SAMPLE_CLUBS)
        clubs = fetch_all_clubs()
        by_name = {c["name"]: c for c in clubs}
        assert by_name["Facebook Club"]["website"] == ""
        assert "facebook.com" in by_name["Facebook Club"]["facebook"]

    @patch("src.clubs.requests.get")
    def test_deduplication(self, mock_get):
        duplicate = self._SAMPLE_CLUBS + [self._SAMPLE_CLUBS[0]]
        mock_get.return_value = self._make_response(duplicate)
        clubs = fetch_all_clubs()
        names = [c["name"] for c in clubs]
        assert names.count("Test Swim Club") == 1

    @patch("src.clubs.requests.get")
    def test_jsonp_without_wrapper(self, mock_get):
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.text = json.dumps(self._SAMPLE_CLUBS[:1])
        mock_get.return_value = mock
        clubs = fetch_all_clubs()
        assert len(clubs) == 1

    @patch("src.clubs.requests.get")
    def test_network_error_returns_empty(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException("timeout")
        clubs = fetch_all_clubs()
        assert clubs == []
