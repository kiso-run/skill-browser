"""skill-browser — headless WebKit automation via Playwright.

Subprocess contract (same as all kiso skills):
  stdin:  JSON {args, session, workspace, session_secrets, plan_outputs}
  stdout: result text on success
  stderr: error description on failure
  exit 0: success, exit 1: failure
"""
from __future__ import annotations

import json
import re
import signal
import sys
from pathlib import Path

signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

# Selectors for elements included in the numbered snapshot.
_SNAPSHOT_SELECTORS = (
    "a, button, input, select, textarea, "
    "[role='button'], [role='link'], [role='checkbox'], "
    "[role='radio'], [role='menuitem']"
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    data = json.load(sys.stdin)
    args = data["args"]
    workspace = Path(data.get("workspace", "/tmp"))
    action = args.get("action", "snapshot")

    browser_dir = workspace / ".browser"
    browser_dir.mkdir(parents=True, exist_ok=True)
    state_file = browser_dir / "state.json"

    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        print(
            "Playwright is not installed. Re-run: kiso skill install skill-browser",
            file=sys.stderr,
        )
        sys.exit(1)

    with sync_playwright() as p:
        context = p.webkit.launch_persistent_context(
            user_data_dir=str(browser_dir / "profile"),
            headless=True,
        )
        try:
            result = dispatch(action, args, context, state_file)
            print(result)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        finally:
            context.close()


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def dispatch(action: str, args: dict, context, state_file: Path) -> str:
    page = context.new_page()
    if action == "navigate":
        return do_navigate(page, args, state_file)
    if action == "snapshot":
        return do_snapshot(page, args, state_file)
    if action == "click":
        return do_click(page, args, state_file)
    if action == "fill":
        return do_fill(page, args, state_file)
    if action == "screenshot":
        return do_screenshot(page, args, state_file)
    raise ValueError(f"Unknown action: {action!r}. Use: navigate, snapshot, click, fill, screenshot")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def do_navigate(page, args: dict, state_file: Path) -> str:
    url = args.get("url", "").strip()
    if not url:
        raise ValueError("navigate: 'url' argument is required")
    page.goto(url, timeout=30000)
    save_state(state_file, page.url)
    return f"Navigated to: {page.title()}\nURL: {page.url}"


def do_snapshot(page, args: dict, state_file: Path) -> str:
    current_url = load_state(state_file)
    if not current_url:
        raise ValueError("No current page. Use action='navigate' first.")
    page.goto(current_url, timeout=30000)
    save_state(state_file, page.url)
    return snapshot(page)


def do_click(page, args: dict, state_file: Path) -> str:
    current_url = load_state(state_file)
    if not current_url:
        raise ValueError("No current page. Use action='navigate' first.")
    ref = args.get("element", "").strip()
    if not ref:
        raise ValueError("click: 'element' argument is required")
    page.goto(current_url, timeout=30000)
    click_element(page, ref)
    save_state(state_file, page.url)
    return f"Clicked {ref!r}. URL: {page.url}\n\n{snapshot(page)}"


def do_fill(page, args: dict, state_file: Path) -> str:
    current_url = load_state(state_file)
    if not current_url:
        raise ValueError("No current page. Use action='navigate' first.")
    ref = args.get("element", "").strip()
    if not ref:
        raise ValueError("fill: 'element' argument is required")
    value = args.get("value", "")
    page.goto(current_url, timeout=30000)
    fill_element(page, ref, value)
    save_state(state_file, page.url)
    return f"Filled {ref!r}. URL: {page.url}\n\n{snapshot(page)}"


def do_screenshot(page, args: dict, state_file: Path) -> str:
    current_url = load_state(state_file)
    if not current_url:
        raise ValueError("No current page. Use action='navigate' first.")
    page.goto(current_url, timeout=30000)
    out_path = state_file.parent.parent / "screenshot.png"
    page.screenshot(path=str(out_path))
    return f"Screenshot saved: {out_path}"


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def snapshot(page) -> str:
    """Return a numbered list of interactive elements for the current page."""
    elements = page.query_selector_all(_SNAPSHOT_SELECTORS)
    lines = [f"Page: {page.title()}", f"URL: {page.url}", ""]
    for i, el in enumerate(elements, 1):
        lines.append(f"[{i}] {_describe_element(el)}")
    if not elements:
        lines.append("(no interactive elements found)")
    return "\n".join(lines)


def _describe_element(el) -> str:
    tag = el.evaluate("e => e.tagName.toLowerCase()")
    parts = [f"<{tag}"]
    for attr in ("type", "name", "placeholder", "href"):
        v = el.get_attribute(attr)
        if v:
            parts.append(f' {attr}="{v[:80]}"')
    text = (el.inner_text() or "").strip()[:80]
    if text:
        parts.append(f">{text}</{tag}>")
    else:
        parts.append(">")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Element resolution
# ---------------------------------------------------------------------------

def resolve_element(page, ref: str):
    """Resolve a [N] reference or CSS selector to a Playwright element handle."""
    m = re.match(r"^\[?(\d+)\]?$", ref.strip())
    if m:
        n = int(m.group(1)) - 1
        elements = page.query_selector_all(_SNAPSHOT_SELECTORS)
        if 0 <= n < len(elements):
            return elements[n]
        raise ValueError(
            f"Element [{int(m.group(1))}] not found (page has {len(elements)} elements)"
        )
    el = page.query_selector(ref)
    if el:
        return el
    raise ValueError(f"Element not found: {ref!r}")


def click_element(page, ref: str) -> None:
    el = resolve_element(page, ref)
    el.click()
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass  # navigation may not have occurred


def fill_element(page, ref: str, value: str) -> None:
    el = resolve_element(page, ref)
    el.fill(value)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def save_state(state_file: Path, url: str) -> None:
    state_file.write_text(json.dumps({"url": url}))


def load_state(state_file: Path) -> str | None:
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text()).get("url")
    except Exception:
        return None


if __name__ == "__main__":
    main()
