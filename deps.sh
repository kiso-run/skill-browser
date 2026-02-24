#!/usr/bin/env bash
# Install the Playwright WebKit browser binary.
# uv sync must have already run so the playwright package is available.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/.venv/bin/playwright" install webkit
