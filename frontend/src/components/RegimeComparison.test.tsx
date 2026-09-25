import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { RegimeComparisonView } from "./RegimeComparison";
import type { RegimeComparison } from "../types/tax";

const regime = (surcharge: string) => ({
  income: { gross_total_income: "6150000", chapter_via_total: "0", standard_deduction: "50000", total_income: "6150000" },
  tax_after_rebate: "1657500", surcharge, cess: "72930", total_tax_liability: "1896180",
  taxes_paid_total: "1621620", refund_due: "0", tax_payable: "299400",
});

const comparison = {
  old: regime("165750"),
  new: { ...regime("0"), total_tax_liability: "1621620" },
  recommended: "new",
  savings: "274560",
  breakeven_deduction_amount: "850000",
  deltas: [
    { line: "Gross salary", old_value: "6200000.00", new_value: "6200000.00", delta: "0.00" },
    { line: "Standard deduction", old_value: "50000", new_value: "75000", delta: "25000" },
  ],
} as unknown as RegimeComparison;

describe("RegimeComparisonView", () => {
  const html = renderToStaticMarkup(<RegimeComparisonView comparison={comparison} />);

  it("treats string zero deltas as no change", () => {
    expect(html).toMatch(/Gross salary<\/td>.*?td-diff\s*">—</);
    expect(html).toContain("▲ ₹ 25,000");
  });

  it("shows surcharge so the card adds up to total liability", () => {
    expect(html).toContain("Surcharge");
    expect(html).toContain("₹ 1,65,750");
  });

  it("names the cheaper regime as the simulator winner", () => {
    expect(html).toContain("New wins by ₹ 2,74,560");
  });

  it("does not subtract the standard deduction twice", () => {
    expect(html).toContain("Chapter VI-A deductions");
    expect(html).not.toContain("− ₹ 50,000");
  });
});
