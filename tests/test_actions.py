"""Tests for do_snapshot, do_click, do_fill, do_screenshot, resolve_element."""
import pytest
from unittest.mock import MagicMock, call

from run import (
    _TIMEOUT_ACTION_MS,
    click_element,
    do_click,
    do_fill,
    do_screenshot,
    do_snapshot,
    fill_element,
    resolve_element,
    save_state,
)
from conftest import make_mock_element, make_mock_page


# ---------------------------------------------------------------------------
# do_snapshot
# ---------------------------------------------------------------------------

def test_snapshot_requires_navigate(tmp_path):
    state_file = tmp_path / "state.json"
    page = make_mock_page()
    with pytest.raises(ValueError, match="navigate"):
        do_snapshot(page, {}, state_file)


def test_snapshot_restores_url(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    page = make_mock_page(url="https://example.com", elements=[])
    do_snapshot(page, {}, state_file)
    page.goto.assert_called_once_with("https://example.com", timeout=30000)


def test_snapshot_returns_numbered_list(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    elements = [
        make_mock_element("a", "Link A"),
        make_mock_element("button", "OK"),
    ]
    page = make_mock_page(elements=elements)
    result = do_snapshot(page, {}, state_file)
    assert "[1]" in result
    assert "[2]" in result


# ---------------------------------------------------------------------------
# do_click
# ---------------------------------------------------------------------------

def test_click_requires_navigate(tmp_path):
    page = make_mock_page()
    with pytest.raises(ValueError, match="navigate"):
        do_click(page, {"element": "[1]"}, tmp_path / "state.json")


def test_click_requires_element(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    page = make_mock_page()
    with pytest.raises(ValueError, match="'element' argument is required"):
        do_click(page, {}, state_file)


def test_click_by_number(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    el = make_mock_element("button", "Submit")
    page = make_mock_page(elements=[el])
    do_click(page, {"element": "[1]"}, state_file)
    el.click.assert_called_once()


def test_click_updates_state(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    el = make_mock_element("a", "Next")
    page = make_mock_page(url="https://example.com/page2", elements=[el])
    do_click(page, {"element": "[1]"}, state_file)
    from run import load_state
    assert load_state(state_file) == "https://example.com/page2"


# ---------------------------------------------------------------------------
# do_fill
# ---------------------------------------------------------------------------

def test_fill_requires_navigate(tmp_path):
    page = make_mock_page()
    with pytest.raises(ValueError, match="navigate"):
        do_fill(page, {"element": "[1]", "value": "hello"}, tmp_path / "state.json")


def test_fill_requires_element(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    page = make_mock_page()
    with pytest.raises(ValueError, match="'element' argument is required"):
        do_fill(page, {"value": "hello"}, state_file)


def test_fill_by_number(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    el = make_mock_element("input", "", {"type": "text"})
    page = make_mock_page(elements=[el])
    result = do_fill(page, {"element": "[1]", "value": "test value"}, state_file)
    el.fill.assert_called_once_with("test value", timeout=_TIMEOUT_ACTION_MS)
    assert "with: 'test value'" in result


def test_fill_empty_value(tmp_path):
    state_file = tmp_path / "state.json"
    save_state(state_file, "https://example.com")
    el = make_mock_element("input", "", {"type": "text"})
    page = make_mock_page(elements=[el])
    do_fill(page, {"element": "[1]"}, state_file)
    el.fill.assert_called_once_with("", timeout=_TIMEOUT_ACTION_MS)


# ---------------------------------------------------------------------------
# do_screenshot
# ---------------------------------------------------------------------------

def test_screenshot_requires_navigate(tmp_path):
    page = make_mock_page()
    with pytest.raises(ValueError, match="navigate"):
        do_screenshot(page, {}, tmp_path / "state.json")


def test_screenshot_saves_to_workspace(tmp_path):
    state_file = tmp_path / ".browser" / "state.json"
    state_file.parent.mkdir(parents=True)
    save_state(state_file, "https://example.com")
    page = make_mock_page()
    result = do_screenshot(page, {}, state_file)
    assert "screenshot.png" in result
    page.screenshot.assert_called_once()
    call_path = page.screenshot.call_args[1]["path"]
    assert call_path.endswith("screenshot.png")


# ---------------------------------------------------------------------------
# resolve_element
# ---------------------------------------------------------------------------

def test_resolve_by_number(tmp_path):
    el1 = make_mock_element("a", "First")
    el2 = make_mock_element("button", "Second")
    page = make_mock_page(elements=[el1, el2])
    assert resolve_element(page, "[1]") is el1
    assert resolve_element(page, "[2]") is el2


def test_resolve_by_number_without_brackets(tmp_path):
    el = make_mock_element("a", "Link")
    page = make_mock_page(elements=[el])
    assert resolve_element(page, "1") is el


def test_resolve_out_of_range():
    page = make_mock_page(elements=[make_mock_element("a", "Only one")])
    with pytest.raises(ValueError, match=r"\[5\] not found"):
        resolve_element(page, "[5]")


def test_resolve_by_css_selector():
    el = make_mock_element("input", "")
    page = make_mock_page(elements=[])
    page.query_selector.return_value = el
    result = resolve_element(page, "input[name='email']")
    assert result is el
    page.query_selector.assert_called_once_with("input[name='email']")


def test_resolve_css_not_found():
    page = make_mock_page(elements=[])
    page.query_selector.return_value = None
    with pytest.raises(ValueError, match="not found"):
        resolve_element(page, ".nonexistent")


# ---------------------------------------------------------------------------
# click_element / fill_element
# ---------------------------------------------------------------------------

def test_click_element_calls_click():
    el = make_mock_element("button", "Go")
    page = make_mock_page(elements=[el])
    click_element(page, "[1]")
    el.click.assert_called_once()


def test_click_element_swallows_load_state_timeout():
    el = make_mock_element("button", "Go")
    page = make_mock_page(elements=[el])
    page.wait_for_load_state.side_effect = Exception("timeout")
    # Should not raise
    click_element(page, "[1]")


def test_fill_element_calls_fill():
    el = make_mock_element("input", "", {"type": "text"})
    page = make_mock_page(elements=[el])
    fill_element(page, "[1]", "hello world")
    el.fill.assert_called_once_with("hello world", timeout=_TIMEOUT_ACTION_MS)
