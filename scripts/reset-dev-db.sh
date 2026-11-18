#!/usr/bin/env bash
# Drop + recreate the development database, migrate to head, optionally load seed data.
# Usage: scripts/reset-dev-db.sh [--seed]
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec uv run python scripts/reset_db.py --yes "$@"
