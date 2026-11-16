#!/usr/bin/env bash
set -euo pipefail
STUDYMATE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STUDYMATE_ROOT"
STUDYMATE_PYTHON="${PYTHON_BIN:-python3}"
"$STUDYMATE_PYTHON" -c 'import sys; assert sys.version_info >= (3,11), "Требуется Python 3.11 или новее"'
if [ ! -x .venv/bin/python ]; then "$STUDYMATE_PYTHON" -m venv .venv; fi
.venv/bin/python -m pip install --no-cache-dir -r requirements-dev.txt
if [ ! -f frontend/dist/index.html ] || [ "${REBUILD_FRONTEND:-0}" = "1" ]; then
  command -v npm >/dev/null || { echo 'Для сборки нужен Node.js 20+ с npm.'; exit 1; }
  (cd frontend && npm ci --no-audit --no-fund && npm run build)
fi
if [ ! -f .env ]; then cp .env.example .env; fi
PYTHONPATH=backend .venv/bin/python -m studymate init
printf '\nStudyMate готов. Запуск: ./start.command\n'
