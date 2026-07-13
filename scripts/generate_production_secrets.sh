#!/usr/bin/env bash
# Print secrets to paste into Railway Variables (do not commit output).
set -euo pipefail
echo "Paste these into Railway → Project → Variables:"
echo ""
python3 "$(dirname "$0")/generate_encryption_key.py"
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "ADMIN_MASTER_PASSWORD=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"