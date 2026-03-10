"""Tests for do_navigate and _urls_match."""
import pytest
from unittest.mock import MagicMock

from run import _urls_match, do_navigate, load_state, save_state
from conftest import make_mock_element, make_mock_page


def test_navigate_success(tmp_path):
    state_file = tmp_path / "state.json"
    page = make_mock_page(url="https://example.com", title="Example Domain")
    result = do_navigate(page, {"url": "https://example.com"}, state_file)
    assert "Example Domain" in result
    assert "https://example.com" in result
    page.goto.assert_called_once_with("https://example.com", timeout=30000)


def test_navigate_saves_state(tmp_path):
    state_file = tmp_path / "state.json"
    page = make_mock_page(url="https://example.com/redirected")
    do_navigate(page, {"url": "https://example.com"}, state_file)
    # State should reflect the final URL (after any redirect)
    assert load_state(state_file) == "https://example.com/redirected"


def test_navigate_missing_url(tmp_path):
    state_file = tmp_path / "state.json"
    page = make_mock_page()
    with pytest.raises(ValueError, match="'url' argument is required"):
        do_navigate(page, {}, state_file)


def test_navigate_empty_url(tmp_path):
    state_file = tmp_path / "state.json"
    page = make_mock_page()
    with pytest.raises(ValueError, match="'url' argument is required"):
        do_navigate(page, {"url": "   "}, state_file)


# ---------------------------------------------------------------------------
# _urls_match
# ---------------------------------------------------------------------------

class TestUrlsMatch:
    def test_identical_urls(self):
        assert _urls_match("https://example.com/page", "https://example.com/page")

    def test_trailing_slash_ignored(self):
        assert _urls_match("https://example.com/page/", "https://example.com/page")
        assert _urls_match("https://example.com/page", "https://example.com/page/")

    def test_fragment_ignored(self):
        assert _urls_match("https://example.com/page#section", "https://example.com/page")
        assert _urls_match("https://example.com/page", "https://example.com/page#top")

    def test_query_matters(self):
        assert not _urls_match("https://example.com/page?q=1", "https://example.com/page?q=2")
        assert _urls_match("https://example.com/page?q=1", "https://example.com/page?q=1")

    def test_different_paths(self):
        assert not _urls_match("https://example.com/a", "https://example.com/b")

    def test_different_schemes(self):
        assert not _urls_match("http://example.com", "https://example.com")

    def test_different_hosts(self):
        assert not _urls_match("https://a.com/page", "https://b.com/page")


# ---------------------------------------------------------------------------
# navigate dedup
# ---------------------------------------------------------------------------

class TestNavigateDedup:
    def test_skips_reload_when_already_on_url(self, tmp_path):
        state_file = tmp_path / "state.json"
        save_state(state_file, "https://example.com")
        page = make_mock_page(url="https://example.com", title="Example")
        result = do_navigate(page, {"url": "https://example.com"}, state_file)
        assert "Already on" in result
        # goto is called once (to restore the page), not twice
        page.goto.assert_called_once()

    def test_skips_reload_trailing_slash_difference(self, tmp_path):
        state_file = tmp_path / "state.json"
        save_state(state_file, "https://example.com/page/")
        page = make_mock_page(url="https://example.com/page/", title="Page")
        result = do_navigate(page, {"url": "https://example.com/page"}, state_file)
        assert "Already on" in result

    def test_navigates_when_url_differs(self, tmp_path):
        state_file = tmp_path / "state.json"
        save_state(state_file, "https://example.com/old")
        page = make_mock_page(url="https://example.com/new", title="New")
        result = do_navigate(page, {"url": "https://example.com/new"}, state_file)
        assert "Navigated to" in result
        assert "Already on" not in result

    def test_navigates_when_no_prior_state(self, tmp_path):
        state_file = tmp_path / "state.json"
        page = make_mock_page(url="https://example.com", title="Example")
        result = do_navigate(page, {"url": "https://example.com"}, state_file)
        assert "Navigated to" in result

    def test_dedup_returns_snapshot(self, tmp_path):
        state_file = tmp_path / "state.json"
        save_state(state_file, "https://example.com")
        el = make_mock_element("button", "Click me")
        page = make_mock_page(url="https://example.com", title="Example", elements=[el])
        result = do_navigate(page, {"url": "https://example.com"}, state_file)
        assert "[1]" in result
        assert "Click me" in result
