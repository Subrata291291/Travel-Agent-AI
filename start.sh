#!/usr/bin/env bash
set -euo pipefail

# Keep the deployed database schema in sync before the API accepts requests.
alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
