#!/usr/bin/env bash
# Run the Celery worker locally without Docker (requires Redis running locally,
# or set CELERY_TASK_ALWAYS_EAGER=true in .env to skip Celery/Redis entirely
# for a quick demo where the pipeline runs inline on upload).
set -e
cd "$(dirname "$0")/../backend"
export PYTHONPATH="$(pwd):$(pwd)/.."
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
