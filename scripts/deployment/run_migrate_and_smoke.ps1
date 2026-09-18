Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "==> Running Alembic migrations"
docker compose -f docker-compose.yml exec backend python -m alembic -c /app/alembic.ini upgrade head

Write-Host "==> Running ETL ingest (seed + parquet + registry + forecast)"
docker compose -f docker-compose.yml exec backend python -m etl.ingest_seed
docker compose -f docker-compose.yml exec backend python -m etl.ingest_parquet
docker compose -f docker-compose.yml exec backend python -m etl.ingest_ml_registry
docker compose -f docker-compose.yml exec backend python -m etl.build_fuel_forecast

Write-Host "==> Verifying ETL counters"
docker compose -f docker-compose.yml exec backend python -m etl.verify

Write-Host "==> Running smoke checks"
python scripts/deployment/smoke_check.py

Write-Host "==> Done"
