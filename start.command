#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist/index.html ]; then ./scripts/setup.sh; fi
printf '\nStudyMate откроется по адресу http://127.0.0.1:8000\nОстановка: Ctrl+C в этом окне.\n\n'
export PYTHONPATH=backend
exec .venv/bin/python -m studymate serve --port 8000
