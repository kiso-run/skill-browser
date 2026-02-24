"""Tests for snapshot and _describe_element."""
import pytest

from run import _describe_element, snapshot
from conftest import make_mock_element, make_mock_page


def test_snapshot_empty_page():
    page = make_mock_page(elements=[])
    result = snapshot(page)
    assert "Page: Test Page" in result
    assert "URL: https://example.com" in result
    assert "no interactive elements" in result


def test_snapshot_with_elements():
    elements = [
        make_mock_element("a", "Home", {"href": "/"}),
        make_mock_element("button", "Submit"),
        make_mock_element("input", "", {"type": "text", "placeholder": "Enter name"}),
    ]
    page = make_mock_page(elements=elements)
    result = snapshot(page)
    assert "[1]" in result
    assert "[2]" in result
    assert "[3]" in result
    assert "Home" in result
    assert "Submit" in result
    assert 'placeholder="Enter name"' in result


def test_snapshot_numbered_sequentially():
    elements = [make_mock_element("a", f"Link {i}") for i in range(5)]
    page = make_mock_page(elements=elements)
    result = snapshot(page)
    for i in range(1, 6):
        assert f"[{i}]" in result


def test_describe_element_link():
    el = make_mock_element("a", "About", {"href": "https://example.com/about"})
    desc = _describe_element(el)
    assert desc.startswith("<a")
    assert 'href="https://example.com/about"' in desc
    assert "About" in desc


def test_describe_element_input():
    el = make_mock_element("input", "", {"type": "email", "placeholder": "Email"})
    desc = _describe_element(el)
    assert 'type="email"' in desc
    assert 'placeholder="Email"' in desc


def test_describe_element_button_no_text():
    el = make_mock_element("button", "")
    desc = _describe_element(el)
    assert desc.startswith("<button")
    assert desc.endswith(">")


def test_describe_element_truncates_long_text():
    long_text = "x" * 200
    el = make_mock_element("a", long_text)
    desc = _describe_element(el)
    # inner_text is truncated to 80 chars in _describe_element
    assert len(desc) < 200


def test_describe_element_truncates_long_href():
    long_href = "https://example.com/" + "a" * 200
    el = make_mock_element("a", "Link", {"href": long_href})
    desc = _describe_element(el)
    assert len(desc.split('href="')[1].split('"')[0]) <= 80
