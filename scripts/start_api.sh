#!/bin/sh
set -eu

python3 -m pip install -e .
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
