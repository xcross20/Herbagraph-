#!/usr/bin/env bash
# Back-compat wrapper — use scripts/playwright_ui_smoke.sh
exec "$(dirname "$0")/playwright_ui_smoke.sh" "$@"