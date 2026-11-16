#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
APP_MODE=demo DATABASE_PATH='' PYTHONPATH=backend .venv/bin/python -m studymate reset-demo
