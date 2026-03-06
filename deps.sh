#!/usr/bin/env bash
# Install system libraries and the Playwright WebKit browser binary.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Install Python dependencies
uv sync

# Install system libraries required by Playwright (libgtk, libcairo, etc.)
uv run playwright install-deps

# Download the WebKit browser binary
uv run playwright install webkit
