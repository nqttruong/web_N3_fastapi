#!/usr/bin/env bash
# Start an isolated backend for Playwright: fresh "<db>_e2e" database on port 8001.
set -euo pipefail
cd "$(dirname "$0")/.."

base_url="$(uv run python -c 'from app.core.config import get_settings; print(get_settings().database_url)')"
e2e_url="${base_url%/*}/$(basename "${base_url##*/}")_e2e"

export DATABASE_URL="$e2e_url"
export CORS_ORIGINS="http://127.0.0.1:3001,http://localhost:3001"
export APP_ENV=test
# Uploaded screenshots go to a throwaway directory
export IMPORT_STORAGE_DIR="${TMPDIR:-/tmp}/jlpt-e2e-imports"
rm -rf "$IMPORT_STORAGE_DIR"
export IMPORT_RATE_LIMIT_PER_MINUTE=1000
uv run python scripts/reset_db.py --database-url "$e2e_url" --yes
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
