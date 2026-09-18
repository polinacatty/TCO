"""Domain layer — pure business logic (TCO calculation, ranking, etc.).

This package MUST NOT import:

- FastAPI, Pydantic models from ``app.api``
- SQLAlchemy ORM models
- Redis client
- pandas, statsmodels (statsmodels is used only at ETL build-time)

Allowed dependencies: Python stdlib, numpy, ``app.core``.
All I/O happens via ``Protocol`` ports defined in :mod:`app.domain.ports`
and implemented by ``app.repositories``.
"""
