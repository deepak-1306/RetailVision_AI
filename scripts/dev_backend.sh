#!/usr/bin/env bash
# Run the FastAPI backend locally without Docker (uses SQLite by default).
set -e
cd "$(dirname "$0")/../backend"
export PYTHONPATH="$(pwd):$(pwd)/.."
pip install -r requirements.txt --break-system-packages
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
