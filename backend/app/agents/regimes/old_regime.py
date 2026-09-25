"""Old Regime Tax Calculation Engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.agents.regimes.base import (
    absorb_basic_exemption,
    basic_exemption_limit,
    cess,
    interest_and_fees,
    rebate_87a,
    round_to_ten,
    slab_tax,
    slab_tax_components,
    special_rate_tax,
    surcharge,
)
from app.schemas.tax import (
    AgeBand,
    HeadwiseIncome,
    IndianTaxpayerData,
    Regime,
    RegimeTaxResult,
    ResidentialStatus,
)
from app.tax_rules.params import TaxYearParams


class OldRegimeCalculator:
    """Computes full tax liability under the opt-in Old Regime."""

    def calculate(
        self,
        data: IndianTaxpayerData,
        income: HeadwiseIncome,
        params: TaxYearParams,
        filing_date: date | None = None,
    ) -> RegimeTaxResult:
        trace: list[str] = list(income.trace)
        regime = Regime.OLD
        reg_params = params.regimes[regime]
        is_resident = data.residential_status != ResidentialStatus.NON_RESIDENT

        # 1. Normal income portion (special rate incomes are taxed separately)
        special_incomes = (
            income.stcg_111a
            + income.ltcg_112a_taxable
            + income.ltcg_112
            + getattr(income, "winnings_115bb", Decimal("0"))
        )
        normal_income = max(Decimal("0"), income.total_income - special_incomes)

        # 2. Slab tax (senior citizen slabs apply only to resident individuals)
        applicable_age = data.age_band if is_resident else AgeBand.BELOW_60
        slabs = reg_params.slabs[applicable_age]
        components = slab_tax_components(normal_income, slabs)
        slab_tax_amount = sum((c["tax"] for c in components), Decimal("0"))
        assert slab_tax_amount == slab_tax(normal_income, slabs)
        trace.append(
            f"Tax on slab income {normal_income} ({applicable_age}) = {slab_tax_amount}"
        )

        # 3. Special-rate tax (residents first absorb unused basic exemption)
        basic_exemption = basic_exemption_limit(slabs)
        special_income = (
            absorb_basic_exemption(income, normal_income, basic_exemption)
            if is_resident
            else income
        )
        special_tax_amount, special_breakdown = special_rate_tax(
            special_income, params.capital_gains
        )
        for sec, amt in special_breakdown.items():
            if amt > Decimal("0"):
                trace.append(f"Special tax u/s {sec} = {amt}")
        tax_before_rebate = slab_tax_amount + special_tax_amount

        # 4. Rebate u/s 87A (eligible against slab tax, 111A, and 112; barred on 112A and 115BB)
        tax_112a = special_breakdown.get("112A", Decimal("0"))
        tax_115bb = special_breakdown.get("115BB", Decimal("0"))
        eligible_special_tax = max(Decimal("0"), special_tax_amount - tax_112a - tax_115bb)
        reb_87a, _ = rebate_87a(
            income.total_income,
            slab_tax_amount,
            eligible_special_tax,
            regime,
            params,
            is_resident,
        )
        tax_after_rebate = max(Decimal("0"), tax_before_rebate - reb_87a)
        if reb_87a > Decimal("0"):
            trace.append(f"Rebate u/s 87A = {reb_87a}")

        # 5. Surcharge (15% cap covers capital gains, not 115BB winnings)
        sur, sur_relief = surcharge(
            income.total_income,
            tax_after_rebate,
            special_tax_amount - tax_115bb,
            regime,
            params,
            applicable_age,
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

        # 8. Prepaid taxes, relief u/s 89/90/91 (capped at liability) and settlement
        relief = min(
            data.taxes_paid.relief_89 + data.taxes_paid.relief_90_91,
            total_tax_liability,
        )
        taxes_paid_total = (
            data.taxes_paid.tds_salary
            + data.taxes_paid.tds_non_salary
            + data.taxes_paid.tcs
            + sum(data.taxes_paid.advance_tax_instalments.values(), Decimal("0"))
            + data.taxes_paid.self_assessment_tax
            + relief
        )

        int_fees = interest_and_fees(
            total_tax_liability,
            taxes_paid_total,
            filing_date,
            params.filing_due_date,
            params,
            total_income=income.total_income,
            data=data,
            basic_exemption=basic_exemption,
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
            (total_tax_liability / income.total_income * Decimal("100"))
            if income.total_income > Decimal("0")
            else Decimal("0")
        )

        return RegimeTaxResult(
            regime=regime,
            income=income,
            tax_on_slab_income=slab_tax_amount,
            slab_components=components,
            tax_on_special_income=special_tax_amount,
            tax_before_rebate=tax_before_rebate,
            rebate_87a=reb_87a,
            marginal_relief_87a=Decimal("0"),
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
