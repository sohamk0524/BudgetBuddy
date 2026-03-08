"""Tests for services.local_deals — parsing, caching, and tag matching."""

import pytest
from services.local_deals import _parse_deals_file, get_deals, match_deals, _deals_cache

# Path to the real deals file
import os
_UC_DAVIS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "documents", "deals", "uc_davis.md"
)


class TestParsing:
    """Verify _parse_deals_file extracts entries correctly from uc_davis.md."""

    def test_parses_all_entries(self):
        deals = _parse_deals_file(_UC_DAVIS_FILE)
        assert len(deals) == 8

    def test_entry_has_required_fields(self):
        deals = _parse_deals_file(_UC_DAVIS_FILE)
        for deal in deals:
            assert "name" in deal
            assert "tags" in deal
            assert isinstance(deal["tags"], list)

    def test_url_stripped_of_markdown(self):
        deals = _parse_deals_file(_UC_DAVIS_FILE)
        for deal in deals:
            url = deal.get("url", "")
            assert "[" not in url, f"Markdown link syntax not stripped: {url}"
            assert "]" not in url

    def test_tags_are_lowercase_list(self):
        deals = _parse_deals_file(_UC_DAVIS_FILE)
        first = deals[0]
        assert all(isinstance(t, str) for t in first["tags"])
        assert all(t == t.lower() for t in first["tags"])


class TestGetDeals:
    """Verify get_deals loads and caches correctly."""

    def setup_method(self):
        _deals_cache.clear()

    def test_returns_deals_for_uc_davis(self):
        deals = get_deals("uc_davis")
        assert len(deals) == 8

    def test_caches_result(self):
        get_deals("uc_davis")
        assert "uc_davis" in _deals_cache

    def test_missing_school_returns_empty(self):
        deals = get_deals("nonexistent_school_xyz")
        assert deals == []

    def test_missing_school_no_error(self):
        # Should not raise
        deals = get_deals("another_fake_school")
        assert isinstance(deals, list)


class TestMatchDeals:
    """Verify match_deals scores and filters correctly."""

    def setup_method(self):
        _deals_cache.clear()

    def test_pizza_beer_matches_woodstocks(self):
        results = match_deals("uc_davis", ["pizza", "beer"])
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert any("Woodstock" in n for n in names)

    def test_thai_matches_sophias(self):
        results = match_deals("uc_davis", ["thai"])
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert any("Sophia" in n for n in names)

    def test_no_match_keywords_returns_empty(self):
        results = match_deals("uc_davis", ["sushi", "ramen", "korean"])
        assert results == []

    def test_missing_school_returns_empty(self):
        results = match_deals("nonexistent_school", ["pizza"])
        assert results == []

    def test_empty_keywords_returns_empty(self):
        results = match_deals("uc_davis", [])
        assert results == []

    def test_max_results_respected(self):
        results = match_deals("uc_davis", ["bar", "drinks", "happy hour"], max_results=2)
        assert len(results) <= 2

    def test_results_sorted_by_score(self):
        # "pizza" + "beer" should rank Woodstock's Bingo (has both) above entries with only one
        results = match_deals("uc_davis", ["pizza", "beer"])
        if len(results) >= 2:
            # First result should have at least as many matching tags as second
            first_tags = set(results[0].get("tags", []))
            second_tags = set(results[1].get("tags", []))
            keywords = {"pizza", "beer"}
            assert len(keywords & first_tags) >= len(keywords & second_tags)

    def test_groceries_match(self):
        results = match_deals("uc_davis", ["groceries"])
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert any("Nugget" in n or "Co-op" in n for n in names)
