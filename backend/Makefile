.PHONY: help install dev up down logs shell test test-unit lint fmt typecheck \
        migrate downgrade ingest ingest-seed ingest-parquet ingest-registry \
        ingest-forecast verify

PYTHON  ?= python
PIP     ?= $(PYTHON) -m pip
UVICORN ?= $(PYTHON) -m uvicorn
PYTEST  ?= $(PYTHON) -m pytest
RUFF    ?= $(PYTHON) -m ruff
MYPY    ?= $(PYTHON) -m mypy
ALEMBIC ?= $(PYTHON) -m alembic
COMPOSE ?= docker compose -f docker/docker-compose.yml

help:
	@echo "TCO backend - common targets"
	@echo "  install            pip install -e .[dev,etl]"
	@echo "  dev                uvicorn with --reload"
	@echo "  up / down          docker compose up -d / down"
	@echo "  logs               tail api container logs"
	@echo "  shell              bash inside api container"
	@echo "  test               pytest"
	@echo "  test-unit          pytest -m unit"
	@echo "  lint               ruff check"
	@echo "  fmt                ruff check --fix + ruff format"
	@echo "  typecheck          mypy app etl"
	@echo ""
	@echo "  migrate            alembic upgrade head"
	@echo "  downgrade          alembic downgrade -1"
	@echo "  ingest             все 4 ингеста: seed -> parquet -> registry -> forecast"
	@echo "    ingest-seed      только CSV из ml/data/seed/"
	@echo "    ingest-parquet   только parquet (car_mods, fuel_prices, cbr) + tire_sizes"
	@echo "    ingest-registry  ml_models / ml_strategies + копия SARIMA .pkl"
	@echo "    ingest-forecast  материализация fuel SARIMA -> fuel_price_forecast"
	@echo "  verify             счётчики строк по всем таблицам"

install:
	$(PIP) install -e ".[dev,etl]"

dev:
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

shell:
	$(COMPOSE) exec api bash

test:
	$(PYTEST)

test-unit:
	$(PYTEST) -m unit

lint:
	$(RUFF) check .

fmt:
	$(RUFF) check . --fix
	$(RUFF) format .

typecheck:
	$(MYPY) app etl

# ---------------------------------------------------------------------------- #
# Database lifecycle                                                           #
# ---------------------------------------------------------------------------- #

migrate:
	$(ALEMBIC) upgrade head

downgrade:
	$(ALEMBIC) downgrade -1

ingest: ingest-seed ingest-parquet ingest-registry ingest-forecast

ingest-seed:
	$(PYTHON) -m etl.ingest_seed

ingest-parquet:
	$(PYTHON) -m etl.ingest_parquet

ingest-registry:
	$(PYTHON) -m etl.ingest_ml_registry

ingest-forecast:
	$(PYTHON) -m etl.build_fuel_forecast

verify:
	$(PYTHON) -m etl.verify
