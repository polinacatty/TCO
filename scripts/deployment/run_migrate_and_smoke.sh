#!/usr/bin/env bash
set -euo pipefail

echo "==> Running Alembic migrations"
docker compose -f docker-compose.yml exec backend python -m alembic -c /app/alembic.ini upgrade head

echo "==> Running ETL ingest (seed + parquet + registry + forecast)"
docker compose -f docker-compose.yml exec backend python -m etl.ingest_seed
docker compose -f docker-compose.yml exec backend python -m etl.ingest_parquet
docker compose -f docker-compose.yml exec backend python -m etl.ingest_ml_registry
docker compose -f docker-compose.yml exec backend python -m etl.build_fuel_forecast

echo "==> Verifying ETL counters"
docker compose -f docker-compose.yml exec backend python -m etl.verify

echo "==> Running smoke checks"
python3 scripts/deployment/smoke_check.py

echo "==> Done"
