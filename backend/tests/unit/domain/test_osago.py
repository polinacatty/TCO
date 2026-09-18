from __future__ import annotations

from decimal import Decimal

from app.domain.profile import StoType, UserProfile
from app.domain.tco.components.osago import OsagoComponent
from app.domain.tco.snapshots import OsagoCoefficientsSnapshot


def test_osago_basic(
    profile_balanced: UserProfile,
    osago_coefficients: OsagoCoefficientsSnapshot,
) -> None:
    tb_mid = (Decimal("1399") + Decimal("8665")) / Decimal(2)
    expected_premium = int(
        (
            tb_mid
            * Decimal("1.96")
            * Decimal("0.95")
            * Decimal("1.00")
            * Decimal("1.20")
            * Decimal("1.00")
            * Decimal("1.00")
        ).quantize(Decimal("1"))
    )

    comp = OsagoComponent()
    total, breakdown = comp.compute(profile_balanced, osago_coefficients)
    assert breakdown.annual_premium_rub == expected_premium
    assert total == expected_premium * 5
    assert breakdown.horizon_years == 5
    assert set(breakdown.coefficients) == {"KT", "KBM", "KVS", "KO", "KM", "KS"}


def test_osago_kvs_changes_premium(
    profile_balanced: UserProfile,
    osago_coefficients: OsagoCoefficientsSnapshot,
) -> None:
    aggressive = OsagoCoefficientsSnapshot(
        tb_min_rub=osago_coefficients.tb_min_rub,
        tb_max_rub=osago_coefficients.tb_max_rub,
        kt_general=osago_coefficients.kt_general,
        km_value=osago_coefficients.km_value,
        kvs_value=Decimal("1.87"),
        ko_value=osago_coefficients.ko_value,
        kbm_value=osago_coefficients.kbm_value,
        ks_value=osago_coefficients.ks_value,
    )
    comp = OsagoComponent()
    safe_total, _ = comp.compute(profile_balanced, osago_coefficients)
    risky_total, _ = comp.compute(profile_balanced, aggressive)
    assert risky_total > safe_total


def test_osago_horizon_scales_linearly(
    osago_coefficients: OsagoCoefficientsSnapshot,
) -> None:
    comp = OsagoComponent()
    p1 = UserProfile(
        horizon_years=1,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
    )
    p2 = UserProfile(
        horizon_years=4,
        mileage_per_year_km=15_000,
        sto_type=StoType.INDEPENDENT,
    )
    t1, _ = comp.compute(p1, osago_coefficients)
    t2, _ = comp.compute(p2, osago_coefficients)
    assert t2 == 4 * t1
