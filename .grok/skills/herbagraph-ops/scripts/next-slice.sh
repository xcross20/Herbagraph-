#!/usr/bin/env bash
# Print the next pending backlog slice (requires jq)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
BACKLOG="$ROOT/ops/BACKLOG.json"
if ! command -v jq >/dev/null 2>&1; then
  echo "Install jq to use next-slice.sh, or read ops/BACKLOG.json directly."
  exit 1
fi
jq -r '.slices | map(select(.status == "pending")) | sort_by(.priority) | .[0] | "\(.id): \(.title)"' "$BACKLOG"