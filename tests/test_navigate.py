"""Tests for do_navigate."""
import pytest
from unittest.mock import MagicMock

from run import do_navigate, load_state
from conftest import make_mock_page


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
