"""
Shared pytest fixtures.

autouse: patch out time.sleep in every module under src/ so tests that
exercise the scraping code (detector.py, clubs.py) don't wait for
politeness delays.
"""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("src.detector.time.sleep"), patch("src.clubs.time.sleep"):
        yield
