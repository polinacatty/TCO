"""User profile DTO — pure dataclass used as input to TCO domain.

The profile carries everything the domain needs about *how* the user plans to
own the car: horizon, mileage, region, type of service station, KASKO flag,
and driver age / experience (used for the OSAGO KVS coefficient).

This is intentionally **decoupled** from the future ``users`` table — at the
domain layer we don't care whether the profile is anonymous, persisted or
ephemeral; we only consume the values needed for the calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StoType(StrEnum):
    """Service station type — affects ``labor_rates`` lookup in maintenance."""

    PRIVATE = "private"
    INDEPENDENT = "independent"
    DEALER = "dealer"


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Inputs required from the user to compute TCO.

    Defaults reflect the "balanced":

    * 5-year horizon
    * 15 000 km / year
    * Moscow (region_id = 1)
    * independent SBO
    * KASKO disabled
    * driver age 35, experience 10 years (mature low-risk profile)
    * limited drivers list (typical retail policy)
    """

    horizon_years: int = 5
    mileage_per_year_km: int = 15_000
    region_id: int = 1
    sto_type: StoType = StoType.INDEPENDENT
    include_kasko: bool = False
    driver_age: int = 35
    driver_experience_years: int = 10
    osago_unlimited_drivers: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.horizon_years <= 10:
            raise ValueError(
                f"horizon_years must be in [1, 10], got {self.horizon_years}"
            )
        if not 1_000 <= self.mileage_per_year_km <= 100_000:
            raise ValueError(
                "mileage_per_year_km must be in [1000, 100000], "
                f"got {self.mileage_per_year_km}"
            )
        if not 18 <= self.driver_age <= 100:
            raise ValueError(f"driver_age must be in [18, 100], got {self.driver_age}")
        if not 0 <= self.driver_experience_years <= 80:
            raise ValueError(
                "driver_experience_years must be in [0, 80], "
                f"got {self.driver_experience_years}"
            )
        if self.driver_experience_years > self.driver_age - 16:
            raise ValueError(
                "driver_experience_years cannot exceed (driver_age − 16): "
                f"got age={self.driver_age}, experience={self.driver_experience_years}"
            )


@dataclass(frozen=True, slots=True)
class CarSelection:
    """Identifies the vehicle to compute TCO for.

    ``modification_id`` is the primary key; ``msrp_override_rub`` lets a user
    type their own purchase price (useful for second-hand or discount cases),
    falling back to the catalog ``msrp_new_rub`` when ``None``.

    ``year_of_manufacture`` is needed for the luxury-tax coefficient (per
    ст. 362 НК РФ + Минпромторг перечень); if missing we default to the
    current calendar year — see ``app.domain.tco.components.transport_tax``.
    """

    modification_id: int
    msrp_override_rub: int | None = None
    year_of_manufacture: int | None = None


__all__ = ["StoType", "UserProfile", "CarSelection"]
