"""Tests for save_state / load_state."""
import json

import pytest

from run import load_state, save_state


def test_save_and_load(tmp_path):
    f = tmp_path / "state.json"
    save_state(f, "https://example.com/page")
    assert load_state(f) == "https://example.com/page"


def test_load_missing(tmp_path):
    assert load_state(tmp_path / "nonexistent.json") is None


def test_load_corrupt(tmp_path):
    f = tmp_path / "state.json"
    f.write_text("not json{{{")
    assert load_state(f) is None


def test_load_missing_url_key(tmp_path):
    f = tmp_path / "state.json"
    f.write_text(json.dumps({"other": "value"}))
    assert load_state(f) is None


def test_save_overwrites(tmp_path):
    f = tmp_path / "state.json"
    save_state(f, "https://first.com")
    save_state(f, "https://second.com")
    assert load_state(f) == "https://second.com"
