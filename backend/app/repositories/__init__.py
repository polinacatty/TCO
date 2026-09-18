"""Repositories — SQLAlchemy implementations of :mod:`app.domain.ports`.

Each repository wraps an :class:`AsyncSession` and converts ORM rows into
domain snapshots. The domain layer **only** sees these snapshots — it never
imports SQLAlchemy types.

The :class:`TcoContextBuilder` orchestrates the repositories to assemble a
:class:`~app.domain.tco.inputs.TcoContext` for a single calculation.
"""

from app.repositories.catalog import SqlCatalogRepository
from app.repositories.context_builder import TcoContextBuilder
from app.repositories.fuel import SqlFuelRepository
from app.repositories.pricing import SqlPricingRepository

__all__ = [
    "SqlCatalogRepository",
    "SqlPricingRepository",
    "SqlFuelRepository",
    "TcoContextBuilder",
]
