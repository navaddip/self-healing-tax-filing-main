"""Preflight invariants for the tax-regime comparison report.

The PDF is a presentation layer.  It may render only a canonical calculation
object that passes these identities; it never repairs or substitutes figures.
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.regimes.base import round_to_ten
from app.schemas.tax import IndianTaxpayerData, RegimeComparison
from app.tax_rules.params import TaxYearParams


def validate_report_model(
    data: IndianTaxpayerData,
    comparison: RegimeComparison,
    params: TaxYearParams,
) -> list[str]:
    failures: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    require(data.assessment_year == params.assessment_year, "assessment year does not match tax-rule pack")
    require(data.financial_year == params.financial_year, "financial year does not match tax-rule pack")

    for result in (comparison.old, comparison.new):
        prefix = result.regime.value
        slab_sum = sum(
            (Decimal(str(component["tax"])) for component in result.slab_components),
            Decimal("0"),
        )
        require(slab_sum == result.tax_on_slab_income, f"{prefix}: slab components do not sum to slab tax")
        require(
            result.tax_before_rebate
            == result.tax_on_slab_income + result.tax_on_special_income,
            f"{prefix}: tax-before-rebate identity failed",
        )
        require(
            sum(result.income.chapter_via.values(), Decimal("0"))
            == result.income.chapter_via_total,
            f"{prefix}: Chapter VI-A components do not sum to total",
        )
        expected_cess = (result.tax_after_rebate + result.surcharge) * params.cess_rate
        require(result.cess == expected_cess, f"{prefix}: cess arithmetic failed")
        require(
            result.total_tax_liability
            == round_to_ten(result.tax_after_rebate + result.surcharge + result.cess),
            f"{prefix}: final tax rounding identity failed",
        )

    require(
        comparison.savings
        == abs(comparison.old.total_tax_liability - comparison.new.total_tax_liability),
        "regime savings do not match tax-liability difference",
    )
    require(
        comparison.current_old_total_reductions
        >= sum(comparison.deductions_forfeited_if_new.values(), Decimal("0")),
        "forfeited benefits exceed total old-regime reductions",
    )
    return failures


def assert_report_model(
    data: IndianTaxpayerData,
    comparison: RegimeComparison,
    params: TaxYearParams,
) -> None:
    failures = validate_report_model(data, comparison, params)
    if failures:
        raise ValueError("Report validation failed: " + "; ".join(failures))


def validate_pdf_bytes(
    pdf_bytes: bytes,
    data: IndianTaxpayerData,
    comparison: RegimeComparison,
    params: TaxYearParams,
) -> list[str]:
    """Extract the generated PDF and compare presentation facts to the model."""
    import fitz
    from app.services.pdf.style import inr

    failures: list[str] = []
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in document)
    normalized_text = " ".join(text.split())
    if document.page_count != 8:
        failures.append(f"expected 8 report pages, found {document.page_count}")

    required_values = {
        "old taxable income": comparison.old.income.total_income,
        "old tax before cess": comparison.old.tax_before_rebate,
        "old final tax": comparison.old.total_tax_liability,
        "new taxable income": comparison.new.income.total_income,
        "new tax before cess": comparison.new.tax_before_rebate,
        "new final tax": comparison.new.total_tax_liability,
        "regime difference": comparison.savings,
        "forfeited benefits total": sum(
            comparison.deductions_forfeited_if_new.values(), Decimal("0")
        ),
        "breakeven reduction": comparison.breakeven_deduction_amount,
    }
    for label, value in required_values.items():
        if inr(value) not in normalized_text:
            failures.append(f"missing {label}: {inr(value)}")

    for section in comparison.old.income.chapter_via:
        if section not in normalized_text:
            failures.append(f"missing Chapter VI-A section {section}")

    if params.assessment_year == "2026-27":
        for obsolete in (
            "Up to 3,00,000 @ 0%",
            "3,00,001 - 7,00,000 @ 5%",
            "Above 15,00,000 @ 30%",
        ):
            if obsolete in normalized_text:
                failures.append(f"obsolete AY slab rendered: {obsolete}")

    has_26as = any(e.source == "Form26AS" for e in data.evidence)
    if not has_26as:
        for unsupported in ("Verified PAN & 26AS", "Reconciled Form 16 & 26AS"):
            if unsupported in normalized_text:
                failures.append(f"unsupported 26AS claim rendered: {unsupported}")
        if "26AS reconciliation pending" not in normalized_text:
            failures.append("missing pending 26AS reconciliation status")

    return failures


def assert_report_pdf(
    pdf_bytes: bytes,
    data: IndianTaxpayerData,
    comparison: RegimeComparison,
    params: TaxYearParams,
) -> None:
    failures = validate_pdf_bytes(pdf_bytes, data, comparison, params)
    if failures:
        raise ValueError("Generated PDF validation failed: " + "; ".join(failures))
