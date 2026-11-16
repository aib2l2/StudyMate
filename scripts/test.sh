#!/usr/bin/env bash
# Full local check — the same steps as .github/workflows/ci.yml.
# E2E=1 ./scripts/test.sh additionally runs the Playwright defense scenario.
set -euo pipefail
cd "$(dirname "$0")/.."
echo '== Backend: ruff'
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
echo '== Backend: pytest + coverage'
.venv/bin/python -m pytest
echo '== Frontend: prettier, eslint, tsc/vite build, vitest'
(cd frontend && npm run check)
if [ "${E2E:-0}" = "1" ]; then
  echo '== End-to-end: Playwright'
  (cd frontend && npm run e2e)
fi
