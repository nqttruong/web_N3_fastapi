#!/usr/bin/env bash
# Run every lint, type check, test and build. Requires PostgreSQL to be running
# (docker compose up -d db). Pass --no-e2e to skip Playwright.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "== backend: ruff / mypy / pytest"
cd "$root/backend"
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q

echo "== frontend: eslint / tsc / vitest / build"
cd "$root/frontend"
npm run lint
npm run typecheck
npm test
npm run build

echo "== chrome extension: typecheck / fixture tests / build"
cd "$root/extension"
npm run check

if [[ "${1:-}" != "--no-e2e" ]]; then
  echo "== frontend: playwright"
  cd "$root/frontend"
  npm run test:e2e
fi
echo "All checks passed."
