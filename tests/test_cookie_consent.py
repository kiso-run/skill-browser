"""Tests for _dismiss_cookie_consent and its integration with do_navigate."""
import pytest
from unittest.mock import MagicMock, call

from run import _dismiss_cookie_consent, do_navigate, save_state
from conftest import make_mock_page


def _make_locator(visible=True):
    """Build a mock locator whose .first returns an element with is_visible/click."""
    btn = MagicMock()
    btn.is_visible.return_value = visible
    locator = MagicMock()
    locator.first = btn
    return locator, btn


class TestDismissCookieConsent:
    def test_clicks_first_visible_button(self):
        page = MagicMock()
        locator, btn = _make_locator(visible=True)
        page.locator.return_value = locator
        result = _dismiss_cookie_consent(page)
        assert result is True
        btn.click.assert_called_once_with(timeout=2000)
        page.wait_for_timeout.assert_called_once_with(500)

    def test_returns_false_when_no_banner(self):
        page = MagicMock()
        locator, btn = _make_locator(visible=False)
        page.locator.return_value = locator
        result = _dismiss_cookie_consent(page)
        assert result is False
        btn.click.assert_not_called()

    def test_continues_on_exception(self):
        page = MagicMock()
        # First selector raises, second succeeds
        call_count = 0
        def locator_side_effect(sel):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("timeout")
            loc, _ = _make_locator(visible=True)
            return loc
        page.locator.side_effect = locator_side_effect
        result = _dismiss_cookie_consent(page)
        assert result is True

    def test_returns_false_when_all_raise(self):
        page = MagicMock()
        page.locator.side_effect = Exception("not found")
        result = _dismiss_cookie_consent(page)
        assert result is False


class TestNavigateCallsDismiss:
    def test_dismiss_called_on_fresh_navigate(self, tmp_path):
        """Cookie consent dismissal runs after a fresh navigation."""
        state_file = tmp_path / "state.json"
        page = make_mock_page(url="https://example.com", title="Example")
        # Make locator return not-visible so _dismiss returns False quickly
        locator, btn = _make_locator(visible=False)
        page.locator.return_value = locator
        result = do_navigate(page, {"url": "https://example.com"}, state_file)
        assert "Navigated to" in result
        # locator was called (dismiss was attempted)
        assert page.locator.called

    def test_dismiss_not_called_on_dedup(self, tmp_path):
        """Cookie consent dismissal does NOT run on dedup (already on URL)."""
        state_file = tmp_path / "state.json"
        save_state(state_file, "https://example.com")
        page = make_mock_page(url="https://example.com", title="Example")
        result = do_navigate(page, {"url": "https://example.com"}, state_file)
        assert "Already on" in result
        # locator should NOT be called — no dismiss on dedup
        page.locator.assert_not_called()
