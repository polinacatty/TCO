"""OSAGO component (`C_osago`).

Uses **pre-resolved** coefficients from
:class:`~app.domain.tco.snapshots.OsagoCoefficientsSnapshot` (the repository
layer is responsible for performing the lookups against ``osago_*`` tables
based on ``UserProfile`` and ``CarSnapshot.power_hp``).

The methodology requires that KVS (driver age × experience) is **always**
taken from the user profile — never a constant.

Formula:

    P_year = TB_mid × KT × KБМ × KVS × KO × KM × KS
    C_osago = round(P_year) × horizon_years
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.profile import UserProfile
from app.domain.tco.snapshots import OsagoCoefficientsSnapshot


@dataclass(frozen=True, slots=True)
class OsagoBreakdown:
    annual_premium_rub: int
    horizon_years: int
    tb_mid_rub: Decimal
    coefficients: dict[str, Decimal]


class OsagoComponent:
    """Compute ``C_osago`` over the user's horizon (annual premium × horizon)."""

    def compute(
        self,
        profile: UserProfile,
        coefficients: OsagoCoefficientsSnapshot,
    ) -> tuple[int, OsagoBreakdown]:
        premium = (
            coefficients.tb_mid_rub
            * coefficients.kt_general
            * coefficients.kbm_value
            * coefficients.kvs_value
            * coefficients.ko_value
            * coefficients.km_value
            * coefficients.ks_value
        )
        annual = int(premium.quantize(Decimal("1")))
        total = annual * profile.horizon_years

        breakdown = OsagoBreakdown(
            annual_premium_rub=annual,
            horizon_years=profile.horizon_years,
            tb_mid_rub=coefficients.tb_mid_rub,
            coefficients={
                "KT": coefficients.kt_general,
                "KBM": coefficients.kbm_value,
                "KVS": coefficients.kvs_value,
                "KO": coefficients.ko_value,
                "KM": coefficients.km_value,
                "KS": coefficients.ks_value,
            },
        )
        return total, breakdown


__all__ = ["OsagoComponent", "OsagoBreakdown"]
