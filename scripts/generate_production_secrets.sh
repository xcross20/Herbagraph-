#!/usr/bin/env bash
# Print secrets to paste into Railway Variables (do not commit output).
set -euo pipefail
echo "Paste these into Railway → Project → Variables:"
echo ""
python3 "$(dirname "$0")/generate_encryption_key.py"
echo "SECRET_KEY=$(openssl rand -hex 32)"