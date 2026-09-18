# TCO Backend

FastAPI-сервис для расчёта совокупной стоимости владения автомобилем (TCO)
и подбора оптимальных моделей (TOPSIS).

## Архитектура (слои)

```
api/         FastAPI routers + Pydantic schemas
  ↓
services/    use-cases, оркестрация, кэш Redis
  ↓             ↘
domain/         repositories/      ← чистая бизнес-логика и SQLA-доступ
infrastructure/                    ← async engine, redis, ORM, artifacts
```

`domain/` не импортирует FastAPI/SQLAlchemy/Redis/pandas. Тестируется как
обычные функции.

## Локальный запуск

```bash
cd backend
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e ".[dev]"

cp .env.example .env            

docker compose -f docker/docker-compose.yml up -d postgres redis

make dev
```

После старта:

- Swagger UI: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Readiness: <http://localhost:8000/health/ready>
- Версия: <http://localhost:8000/version>

## Структура

| Папка | Назначение |
|-------|------------|
| `app/api/` | FastAPI routers + Pydantic schemas |
| `app/services/` | use-cases, кэш, оркестрация |
| `app/domain/` | чистое ядро: TCO, TOPSIS, fuel forecast |
| `app/repositories/` | SQLAlchemy-репозитории |
| `app/infrastructure/` | engine БД, redis, ORM, артефакты |
| `app/core/` | logging, exceptions (RFC 7807), middleware |
| `app/alembic/` | миграции БД (этап 1) |
| `etl/` | ингест seed/parquet/ml_registry в БД |
| `artifacts/` | копии ML-артефактов |
| `tests/` | unit / integration / e2e |
| `docker/` | Dockerfile, docker-compose.yml |

## Команды

```bash
make install
make dev
make up / down
make test
make lint
make fmt
make typecheck
```
