from decimal import Decimal

import app.tax_rules  # noqa: F401  (registers fy_2025_26 and fy_2026_27)
from app.schemas.tax import AgeBand, Regime
from app.tax_rules.params import get_params, progressive_tax
from app.tax_rules.validation import validate_all


def test_new_regime_slab_tax_calculation():
    params = get_params("2025-26")
    new_slabs = params.regimes[Regime.NEW].slabs[AgeBand.BELOW_60]

    # ₹10,00,000: 0-4L (0) + 4L-8L @ 5% (20,000) + 8L-10L @ 10% (20,000) = 40,000
    tax_10l = progressive_tax(Decimal("1000000"), new_slabs)
    assert tax_10l == Decimal("40000")

    # ₹11,00,000: 20,000 + 3,00,000 * 10% = 50,000
    tax_11l = progressive_tax(Decimal("1100000"), new_slabs)
    assert tax_11l == Decimal("50000")

    # ₹11,25,000 (Case 2): 20,000 + 3,25,000 * 10% = 52,500
    tax_11_25l = progressive_tax(Decimal("1125000"), new_slabs)
    assert tax_11_25l == Decimal("52500")

    # ₹13,50,000 (Case 1): 20,000 + 40,000 + 1,50,000 * 15% = 82,500
    tax_13_5l = progressive_tax(Decimal("1350000"), new_slabs)
    assert tax_13_5l == Decimal("82500")


def test_old_regime_slab_tax_calculation():
    params = get_params("2025-26")

    # Below 60 on ₹10,00,000: 2.5L-5L (12,500) + 5L-10L (1,00,000) = 1,12,500
    old_slabs_non_senior = params.regimes[Regime.OLD].slabs[AgeBand.BELOW_60]
    tax_non_senior = progressive_tax(Decimal("1000000"), old_slabs_non_senior)
    assert tax_non_senior == Decimal("112500")

    # Senior (60-80) on ₹10,00,000: 3L-5L (10,000) + 5L-10L (1,00,000) = 1,10,000
    old_slabs_senior = params.regimes[Regime.OLD].slabs[AgeBand.SENIOR_60_80]
    tax_senior = progressive_tax(Decimal("1000000"), old_slabs_senior)
    assert tax_senior == Decimal("110000")


def test_all_registered_years_are_structurally_consistent():
    issues = validate_all()
    assert issues == []


def test_params_registered_for_both_years():
    p_2025 = get_params("2025-26")
    assert p_2025.financial_year == "2025-26"
    assert p_2025.assessment_year == "2026-27"
    assert p_2025.verified is True

    p_2026 = get_params("2026-27")
    assert p_2026.financial_year == "2026-27"
    assert p_2026.assessment_year == "2027-28"
    assert p_2026.section_map.get("115BAC") == "202"
    assert p_2026.section_map.get("80C") == "123"
