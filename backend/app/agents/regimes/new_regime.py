"""New Regime Tax Calculation Engine (Section 115BAC(1A))."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.agents.regimes.base import (
    cess,
    interest_and_fees,
    rebate_87a,
    round_to_ten,
    slab_tax,
    special_rate_tax,
    surcharge,
)
from app.schemas.tax import (
    HeadwiseIncome,
    IndianTaxpayerData,
    Regime,
    RegimeTaxResult,
    ResidentialStatus,
)
from app.tax_rules.params import TaxYearParams


class NewRegimeCalculator:
    """Computes full tax liability under the default New Regime u/s 115BAC(1A)."""

    def calculate(
        self,
        data: IndianTaxpayerData,
        income: HeadwiseIncome,
        params: TaxYearParams,
        filing_date: date | None = None,
    ) -> RegimeTaxResult:
        trace: list[str] = list(income.trace)
        regime = Regime.NEW
        reg_params = params.regimes[regime]
        is_resident = data.residential_status != ResidentialStatus.NON_RESIDENT

        # 1. Normal income portion
        special_gains = (
            income.stcg_111a + income.ltcg_112a_taxable + income.ltcg_112
        )
        normal_income = max(Decimal("0"), income.total_income - special_gains)

        # 2. Slab tax (same across all age bands in new regime)
        slabs = reg_params.slabs[data.age_band]
        slab_tax_amount = slab_tax(normal_income, slabs)
        trace.append(f"Tax on slab income {normal_income} = {slab_tax_amount}")

        # 3. Special-rate tax
        special_tax_amount, special_breakdown = special_rate_tax(
            income, params.capital_gains
        )
        for sec, amt in special_breakdown.items():
            if amt > Decimal("0"):
                trace.append(f"Special tax u/s {sec} = {amt}")
        tax_before_rebate = slab_tax_amount + special_tax_amount

        # 4. Rebate u/s 87A and Marginal Relief
        reb_87a, relief_87a = rebate_87a(
            income.total_income,
            slab_tax_amount,
            special_tax_amount,
            regime,
            params,
            is_resident,
        )
        tax_after_rebate = max(
            Decimal("0"),
            (slab_tax_amount - reb_87a - relief_87a) + special_tax_amount,
        )
        if reb_87a > Decimal("0"):
            trace.append(f"Rebate u/s 87A = {reb_87a}")
        if relief_87a > Decimal("0"):
            trace.append(f"Section 87A Marginal Relief = {relief_87a}")

        # 5. Surcharge
        sur, sur_relief = surcharge(
            income.total_income,
            tax_after_rebate,
            special_tax_amount,
            regime,
            params,
            data.age_band,
        )
        tax_plus_surcharge = tax_after_rebate + sur
        if sur > Decimal("0"):
            trace.append(f"Surcharge = {sur} (marginal relief {sur_relief})")

        # 6. Health & Education Cess @ 4%
        cess_amount = cess(tax_plus_surcharge, params.cess_rate)
        trace.append(f"Health & Education Cess @ 4% = {cess_amount}")

        # 7. Total Tax Liability (Section 288B rounding)
        total_tax_liability = round_to_ten(tax_plus_surcharge + cess_amount)
        trace.append(f"Total Tax Liability (rounded) = {total_tax_liability}")

        # 8. Prepaid taxes and settlement
        taxes_paid_total = (
            data.taxes_paid.tds_salary
            + data.taxes_paid.tds_non_salary
            + data.taxes_paid.tcs
            + sum(data.taxes_paid.advance_tax_instalments.values(), Decimal("0"))
            + data.taxes_paid.self_assessment_tax
        )

        int_fees = interest_and_fees(
            total_tax_liability,
            taxes_paid_total,
            filing_date,
            date(2026, 7, 31),
            params,
            total_income=income.total_income,
        )

        net_settlement = (total_tax_liability + sum(int_fees.values(), Decimal("0"))) - taxes_paid_total

        refund_due = Decimal("0")
        tax_payable = Decimal("0")
        if net_settlement < Decimal("0"):
            refund_due = abs(net_settlement)
            trace.append(f"Refund Due = {refund_due}")
        else:
            tax_payable = net_settlement
            trace.append(f"Tax Payable = {tax_payable}")

        effective_rate = (
            (total_tax_liability / income.gross_total_income * Decimal("100"))
            if income.gross_total_income > Decimal("0")
            else Decimal("0")
        )

        return RegimeTaxResult(
            regime=regime,
            income=income,
            tax_on_slab_income=slab_tax_amount,
            tax_on_special_income=special_tax_amount,
            tax_before_rebate=tax_before_rebate,
            rebate_87a=reb_87a,
            marginal_relief_87a=relief_87a,
            tax_after_rebate=tax_after_rebate,
            surcharge=sur,
            surcharge_marginal_relief=sur_relief,
            cess=cess_amount,
            total_tax_liability=total_tax_liability,
            taxes_paid_total=taxes_paid_total,
            interest_234a=int_fees["interest_234a"],
            interest_234b=int_fees["interest_234b"],
            interest_234c=int_fees["interest_234c"],
            fee_234f=int_fees["fee_234f"],
            refund_due=refund_due,
            tax_payable=tax_payable,
            effective_tax_rate=effective_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            trace=trace,
        )
