# Indian Income Tax Statutory Coverage

Comprehensive tracking of statutory provisions implemented in the deterministic tax engines for FY 2025-26 (AY 2026-27).

## 1. Five Heads of Income

| Section / Rule | Description | Engine Implementation | Regime Applicability | Status |
|---|---|---|---|---|
| **Sec 15, 17(1)-(3)** | Salaries (Basic, DA, Bonus, Perquisites, Profits in lieu) | Aggregated across all Form 16s with cross-footing verification | Both | Verified |
| **Sec 10(13A)** | House Rent Allowance (HRA) Exemption | Least of 3: (a) Actual HRA, (b) 50% basic (metro) / 40% (non-metro), (c) Rent paid - 10% basic | Old Regime only (Disallowed in New) | Verified |
| **Sec 16(ia)** | Standard Deduction on Salary | ₹75,000 (New Regime) / ₹50,000 (Old Regime), capped at salary | Both (different limits) | Verified |
| **Sec 16(iii)** | Tax on Employment (Professional Tax) | Deductible up to state statutory maximum (₹2,500) | Old Regime only | Verified |
| **Sec 22-27** | Income from House Property | GAV less municipal taxes = NAV; 30% standard deduction u/s 24(a) | Both | Verified |
| **Sec 24(b)** | Interest on Borrowed Capital (Home Loan) | Self-occupied capped at ₹2,00,000 (Old), ₹0 (New); Let-out fully deductible | Both | Verified |
| **Sec 71(3A)** | House Property Loss Set-off | Capped at ₹2,00,000 against other heads (Old); 0 set-off against other heads (New, carry-forward only) | Old only | Verified |
| **Sec 44AD** | Presumptive Business Income | 6% digital turnover / 8% cash turnover (turnover limit ₹2 Cr / ₹3 Cr) | Both | Verified |
| **Sec 44ADA** | Presumptive Professional Income | 50% gross receipts (receipt limit ₹50 Lakh / ₹75 Lakh) | Both | Verified |
| **Sec 44AE** | Presumptive Goods Carriage | ₹1,000/ton/month (heavy goods > 12T) / ₹7,500/month otherwise | Both | Verified |
| **Sec 111A** | Short-Term Capital Gains (Listed Equity / STT) | Flat 20% (Budget 2024 revised from 15%) | Both | Verified |
| **Sec 112A** | Long-Term Capital Gains (Listed Equity / STT) | 12.5% on gains exceeding ₹1,25,000 annual exemption | Both | Verified |
| **Sec 112** | Long-Term Capital Gains (Property / Unlisted) | 12.5% without indexation; pre-23 July 2024 property computes lower of 12.5% or 20% with CII indexation | Both | Verified |
| **Sec 50AA** | Specified Mutual Funds & Debt MFs | Always treated as short-term capital gains at slab rates | Both | Verified |
| **Sec 56-59** | Income from Other Sources | Bank interest, FD/RD interest, dividends (slab rates), refund interest | Both | Verified |
| **Sec 57(iia)** | Family Pension Deduction | Least of ₹25,000 (New) / ₹15,000 or 1/3rd (Old) | Both (different limits) | Verified |
| **Sec 115BB** | Winnings from Lotteries / Crosswords | Flat 30% tax with no deduction and no Section 87A rebate | Both | Verified |

## 2. Chapter VI-A Deductions

| Section | Description | Statutory Ceiling (FY 2025-26) | New Regime? | Status |
|---|---|---|---|---|
| **80C / 80CCC / 80CCD(1)** | PPF, EPF, ELSS, Life Insurance, Tuition, Home Loan Principal, NPS employee | ₹1,50,000 combined ceiling | No | Verified |
| **80CCD(1B)** | Additional National Pension System (NPS) | ₹50,000 over and above 80C | No | Verified |
| **80CCD(2)** | Employer NPS Contribution | 14% of Basic+DA (New regime), 10% (Old regime private) | Yes | Verified |
| **80D** | Health Insurance Premium | Self/Family: ₹25,000 (₹50,000 senior); Parents: ₹25,000 (₹50,000 senior); Max ₹1,00,000 | No | Verified |
| **80E** | Education Loan Interest | Full interest for up to 8 assessment years | No | Verified |
| **80G** | Donations to Approved Funds | 50% or 100% qualifying limit; cash capped at ₹2,000 | No | Verified |
| **80TTA** | Savings Bank Interest (Below 60) | ₹10,000 ceiling | No | Verified |
| **80TTB** | Interest Income (Senior Citizens 60+) | ₹50,000 ceiling on all deposit interest | No | Verified |

## 3. Tax Slabs, Rebates, and Surcharges

| Feature | New Regime (Sec 115BAC(1A)) | Old Regime | Status |
|---|---|---|---|
| **Slabs** | Up to ₹4L Nil; 4-8L 5%; 8-12L 10%; 12-16L 15%; 16-20L 20%; 20-24L 25%; >24L 30% | Age-banded: <60 (₹2.5L), 60-80 (₹3L), 80+ (₹5L); 5%, 20%, 30% | Verified |
| **Rebate u/s 87A** | Up to ₹60,000 for total income ≤ ₹12,00,000 with marginal relief up to ₹12.7L | Up to ₹12,500 for total income ≤ ₹5,00,000 | Verified |
| **Surcharge** | 10% (50L-1Cr), 15% (1-2Cr), 25% (>2Cr, capped at 25%) | 10% (50L-1Cr), 15% (1-2Cr), 25% (2-5Cr), 37% (>5Cr) | Verified |
| **Special Rate Surcharge Cap** | Capped at 15% on tax from Sec 111A, 112A, 112, and dividends | Capped at 15% on special-rate income | Verified |
| **Surcharge Marginal Relief** | Tax increase cannot exceed income above threshold | Tax increase cannot exceed income above threshold | Verified |
| **Health & Education Cess** | 4% on (Income Tax + Surcharge - Rebate) | 4% on (Income Tax + Surcharge - Rebate) | Verified |
| **Rounding (Sec 288A/B)** | Rounded to nearest ₹10 (ROUND_HALF_UP) | Rounded to nearest ₹10 (ROUND_HALF_UP) | Verified |
| **Form 10-IEA Requirement** | N/A (Default regime) | Required before due date u/s 139(1) for taxpayers with business income | Verified |
