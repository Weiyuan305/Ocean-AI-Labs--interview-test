#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -x .venv/bin/python ]]; then "$PYTHON_BIN" -m venv .venv; fi
PIP_CERT_ARGS=()
if [[ "$(uname -s)" == Darwin && -f /private/etc/ssl/cert.pem ]]; then PIP_CERT_ARGS=(--cert /private/etc/ssl/cert.pem); fi
.venv/bin/python -m pip install "${PIP_CERT_ARGS[@]}" -r requirements.lock
npm ci --prefix frontend
npm run build --prefix frontend
export DB_PATH="${DB_PATH:-data/demo.sqlite3}"
exec .venv/bin/python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port "${PORT:-8000}"
