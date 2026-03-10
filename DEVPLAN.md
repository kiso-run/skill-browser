# skill-browser — Development Plan

## Overview

Headless WebKit browser automation skill for kiso. Allows the planner to
navigate pages, read content, extract links, inspect forms, interact with
elements, and take screenshots — all via a subprocess that communicates over
JSON on stdin/stdout.

**Current status:** v0.1.0 — all core actions implemented and tested with
unit-level mocks. No integration tests against a real browser yet.

## Architecture

```
skill-browser/
├── kiso.toml          # manifest: args schema, deps, usage guide
├── pyproject.toml     # Python deps (playwright >=1.44, pytest)
├── run.py             # entry point + all action logic (~390 LOC)
├── deps.sh            # system libs + WebKit binary installer
├── tests/
│   ├── conftest.py    # shared fixtures and mock builders
│   ├── test_dispatch.py      # dispatch(), main() error paths
│   └── test_read_actions.py  # text/links/forms extraction + _ensure_page
├── README.md
└── LICENSE
```

**Key design decisions:**

- Single-file `run.py` — keeps the skill self-contained; no internal packages.
- Persistent browser profile (`workspace/.browser/profile/`) — cookies and
  session survive between calls within the same kiso session.
- State file (`workspace/.browser/state.json`) — tracks current URL so the
  browser can restore context across invocations.
- Noise stripping in `extract_text` — removes nav, header, footer, cookie
  banners, and ads before extracting body text; prefers `<main>`/`<article>`
  containers.

## Capabilities

| Action     | Description                                        | Status |
|------------|----------------------------------------------------|--------|
| navigate   | Go to a URL, return title + final URL              | done   |
| text       | Extract visible text, strip noise, scope by CSS    | done   |
| links      | Numbered list of links with dedup and filtering    | done   |
| forms      | Structured form field info (inputs, selects, buttons) | done |
| snapshot   | Numbered list of interactive elements `[1]`, `[2]` | done  |
| click      | Click element by `[N]` ref or CSS selector         | done   |
| fill       | Type text into element by `[N]` ref or CSS selector | done  |
| screenshot | Save full-page PNG to workspace                    | done   |

## Milestones

### M1 — Initial skill scaffold ✅

**Problem:** kiso had no browser automation capability.

**Change:**
1. Created `run.py` with subprocess contract (JSON stdin → stdout/stderr)
2. Implemented all 8 actions: navigate, text, links, forms, snapshot, click,
   fill, screenshot
3. Added persistent browser profile and state file for session continuity
4. Defined `kiso.toml` manifest with args schema and usage guide
5. Set up `deps.sh` for system libs + WebKit binary installation

### M2 — Test suite ✅

**Problem:** No automated tests; correctness relied on manual verification.

**Change:**
1. Added `conftest.py` with mock builders (`make_mock_page`,
   `make_mock_element`, `make_input`, `run_skill`)
2. `test_dispatch.py` — covers dispatch routing, navigate, snapshot, click,
   fill, screenshot, text/links/forms delegation, unknown-action error,
   missing-playwright error path
3. `test_read_actions.py` — covers `_ensure_page` (url vs state, redirects),
   `extract_text` (body fallback, content containers, noise stripping,
   selector scoping), `extract_links` (filtering, dedup, scoping),
   `extract_forms` (inputs, selects, textareas, buttons, method default,
   scoping)

### M3 — Read actions: inline URL and selector support ✅

**Problem:** `text`, `links`, and `forms` originally required a prior
`navigate` call. Users had to make two calls to read a new page.

**Change:**
1. Added `_ensure_page` helper — navigates from explicit `url` arg or saved
   state, then saves state
2. All three read actions now accept optional `url` (navigate + extract in one
   step) and `selector` (scope extraction to a CSS subtree)
3. Tests cover both paths (inline URL, state URL) and state persistence after
   redirect

### M4 — Navigate dedup (skip if already on URL) ✅

**Problem:** Planner re-navigates to URLs already loaded. Browser state
persists between calls, so reloading the same page wastes time.

**File:** `run.py` — `do_navigate()`

**Change:**
1. Before `page.goto()`, check if current URL matches target via saved state:
   ```python
   current = load_state(state_file)
   if current and _urls_match(current, url):
       page.goto(current, timeout=30000)
       return f"Already on {url}.\n{snapshot(page)}"
   ```
2. Add `_urls_match(a, b)` helper — normalize trailing slashes, ignore
   fragment:
   ```python
   def _urls_match(a: str, b: str) -> bool:
       from urllib.parse import urlparse
       pa, pb = urlparse(a), urlparse(b)
       return (pa.scheme == pb.scheme and pa.netloc == pb.netloc
               and pa.path.rstrip("/") == pb.path.rstrip("/")
               and pa.query == pb.query)
   ```

**Test:** Navigate to same URL twice — second call returns "Already on..."
without calling `page.goto` a second time.

---

### M5 — Fill action echoes filled value ✅

**Problem:** `do_fill()` returns `Filled '{ref}'. URL: ...` without echoing
the value. Reviewer can't verify the fill succeeded.

**File:** `run.py` — `do_fill()`

**Change:**
1. Change return message to include the value:
   ```python
   return f"Filled {ref!r} with: {value!r}. URL: {page.url}\n\n{snapshot(page)}"
   ```

**Test:** Fill a field — output includes `with: 'the_value'`.

---

### M6 — Cookie consent auto-dismiss

**Problem:** Cookie banners obscure page content and block interactions.

**File:** `run.py` — add `_dismiss_cookie_consent()`

**Change:**
1. Add helper that tries common cookie consent selectors:
   ```python
   _COOKIE_ACCEPT_SELECTORS = [
       "button:has-text('Accept')", "button:has-text('Accetta')",
       "button:has-text('Accept all')", "button:has-text('Accetta tutti')",
       "[id*='cookie'] button:has-text('OK')",
       ".cookie-banner button.accept", "#onetrust-accept-btn-handler",
   ]

   def _dismiss_cookie_consent(page):
       for sel in _COOKIE_ACCEPT_SELECTORS:
           try:
               btn = page.locator(sel).first
               if btn.is_visible(timeout=500):
                   btn.click(timeout=2000)
                   page.wait_for_timeout(500)
                   return True
           except Exception:
               continue
       return False
   ```
2. Call `_dismiss_cookie_consent(page)` at the end of `do_navigate()`, after
   page load.

**Test:** Navigate to a page with a cookie banner — banner dismissed, snapshot
shows page content.

---

### M7 — CAPTCHA detection in snapshot

**Problem:** Forms with CAPTCHA elements cause fill/submit failures. Kiso
should detect and warn early.

**File:** `run.py` — `do_snapshot()`

**Change:**
1. After building the snapshot elements list, scan for CAPTCHA indicators:
   ```python
   _CAPTCHA_MARKERS = [
       "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
       "iframe[src*='turnstile']", ".g-recaptcha", ".h-captcha",
       "[data-sitekey]",
   ]

   def _detect_captcha(page) -> bool:
       for sel in _CAPTCHA_MARKERS:
           if page.query_selector(sel):
               return True
       return False
   ```
2. If CAPTCHA detected, prepend warning to snapshot output:
   ```python
   if _detect_captcha(page):
       lines.insert(0, "CAPTCHA detected on this page. "
                       "Form submission may require human verification.")
   ```

**Test:** Load a page with reCAPTCHA iframe — snapshot output starts with
CAPTCHA warning.

## Milestone Checklist

- [x] **M1** — Initial skill scaffold
- [x] **M2** — Test suite
- [x] **M3** — Read actions: inline URL and selector support
- [x] **M4** — Navigate dedup (skip if already on URL)
- [x] **M5** — Fill action echoes filled value
- [ ] **M6** — Cookie consent auto-dismiss
- [ ] **M7** — CAPTCHA detection in snapshot

## Known Issues / Improvement Ideas

- No integration tests — all tests use mocks; a real-browser test suite
  (against a local HTML fixture server) would catch Playwright API mismatches
- Screenshots are full-page PNG only — no element-scoped or viewport-only
  option, no WebP support
- No timeout configuration — hardcoded 30 s for navigation, 5 s for
  networkidle after click
- No scroll/pagination support — long pages require manual snapshot + click
  workflows
- `extract_text` noise stripping mutates the DOM (removes elements) — if the
  same page object is reused, subsequent calls may miss content
- No JavaScript execution action — cannot run arbitrary JS snippets
- Element resolution re-queries the full snapshot selector list on every
  click/fill — could cache between calls within the same invocation
