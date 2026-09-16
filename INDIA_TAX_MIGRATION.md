# Self-Healing Multi-Agent Tax Filing - India Conversion Plan

**Source repo:** `https://github.com/Ilan-07/self-healing-tax-filing` (US / Form 1040)
**Target:** same architecture, Indian income tax, dual-regime comparison, professional PDF advisory report
**Build tool:** Antigravity (each milestone below is a ready-to-paste prompt)
**Target tax year:** FY 2025-26 (AY 2026-27) as primary, FY 2026-27 (Tax Year 2026-27) registered as a second param pack
**Doc date:** 15 September 2026

---

## 0. Read this before you start

### 0.1 The one invariant you must not break

The US repo's design principle is the reason it works:

> **LLMs read and classify. Deterministic code decides and computes.**

No language model ever produces a rupee figure that lands on the return. The model's only job is to turn a scanned Form 16 into a typed struct with evidence pointers and confidence scores. Every slab, rate, cap, threshold and rebate lives in a versioned Python parameter pack with a citation attached. Keep this. Tax arithmetic authored by an LLM is the single fastest way to fail a demo and the only thing a reviewer will actually attack.

### 0.2 What actually changes, and what does not

| Layer | Change needed |
|---|---|
| LangGraph workflow shape (parse → calculate → verify → remediate/document) | **Almost none.** One new node. |
| Agent count | 5 → **7** (add Regime Comparison, split Income Computation out of Tax Processing) |
| Document reading | **Total rewrite.** W-2 → Form 16 Part A + Part B, Form 26AS, AIS, broker P&L, interest certificates, rent receipts |
| Tax rule packs | **Total rewrite.** `federal_2025.py` + 47 state packs → `fy_2025_26.py` (union only, no state income tax in India) |
| Calculator | **Total rewrite.** Single-path 1040 math → dual-path (old + new regime) run in parallel over the same income facts |
| Verification | Rewrite the check pack; the confidence scoring and gating logic survive as-is |
| Remediation loop | **Keep verbatim.** Bounded self-healing is regime-agnostic |
| PDF output | Rewrite. Form 1040 render → **Regime Comparison Advisory Report** (the headline deliverable) |
| E-file boundary | Adapter pattern survives. IRS MeF → Income Tax Department ERI Type-2 APIs, ITR JSON export as the default |
| Frontend | Minor: add regime comparison panel, INR formatting, Indian date/lakh-crore number formats |

### 0.3 The structural difference that drives everything

The US return is **one computation**. The Indian return is **two computations of the same facts under two different legal regimes**, and the taxpayer picks the cheaper one. That is not a feature bolted on the side; it is the spine of the product.

Concretely:

- The **new regime (Section 115BAC(1A))** is the default since AY 2024-25. Almost no deductions, wider slabs, higher standard deduction (₹75,000), ₹60,000 rebate up to ₹12 lakh total income.
- The **old regime** is opt-in. Narrow slabs, but Chapter VI-A deductions (80C, 80D, 80CCD(1B), 80TTA/TTB, 80G...), HRA, LTA, professional tax, and Section 24(b) home-loan interest on a self-occupied house.
- A salaried person with no business income can switch regimes **every single year**, just by ticking the box in the ITR. A person with business or professional income must file **Form 10-IEA** to opt out, and can come back only once.

So the deliverable is not "your tax is X". It is "under the old regime your tax is X and under the new regime it is Y; here is the ₹Z difference, line by line, here is which one to pick, and here is exactly what you would have to give up or gain by picking the other."

### 0.4 A legal boundary you must build in from day one

You cannot file a real ITR from a college project. There is no open public filing API. Machine filing goes through the **e-Return Intermediary (ERI) Type-2** programme: the Income Tax Department publishes Login, Add Client, Prefill, Validate-and-Submit-ITR, e-Verify and Acknowledgement APIs, and only registered ERIs get credentials. Registration requires an entity, net worth criteria and a DSC.

Therefore, exactly as the US repo does with `EFILE_BACKEND=pdf`:

- **Default backend = `json_self_file`.** The system produces a schema-valid ITR JSON the taxpayer uploads themselves at incometax.gov.in, plus the advisory PDF. No credentials touched.
- **Second backend = `mock_eri`.** Simulates the ERI handshake deterministically so you can demo the adapter swap and the acknowledgement flow.
- Never claim in the UI, README or viva that the system "files your return". It **prepares and packages** a verified return.

Put a `DISCLAIMER.md` in the repo root and a footer line on every PDF page: *"Computer-generated advisory. Not tax advice. Verify with a qualified chartered accountant before filing."*

---

## 1. India tax rulebook (the reference the agent should build from)

Everything in this section is what you hard-code into `backend/app/tax_rules/fy_2025_26.py` with a `source=` citation and `verified=` flag, exactly the way `federal_2025.py` does it. **Do not let the LLM generate these numbers at runtime.**

### 1.1 New regime slabs, Section 115BAC(1A) - FY 2025-26 and FY 2026-27

Budget 2026 left the slabs unchanged, so the same table applies to both years.

| Total income | Rate |
|---|---|
| Up to ₹4,00,000 | Nil |
| ₹4,00,001 - ₹8,00,000 | 5% |
| ₹8,00,001 - ₹12,00,000 | 10% |
| ₹12,00,001 - ₹16,00,000 | 15% |
| ₹16,00,001 - ₹20,00,000 | 20% |
| ₹20,00,001 - ₹24,00,000 | 25% |
| Above ₹24,00,000 | 30% |

No age-based variation. Senior and super-senior citizens get the same ₹4 lakh basic exemption under the new regime.

### 1.2 Old regime slabs - FY 2025-26

| Total income | Below 60 | Senior (60-80) | Super senior (80+) |
|---|---|---|---|
| Basic exemption | ₹2,50,000 | ₹3,00,000 | ₹5,00,000 |
| 5% band | ₹2.5L - ₹5L | ₹3L - ₹5L | n/a |
| 20% band | ₹5L - ₹10L | ₹5L - ₹10L | ₹5L - ₹10L |
| 30% band | Above ₹10L | Above ₹10L | Above ₹10L |

Age is determined **at any time during the previous year**. A non-resident individual gets the ₹2.5 lakh exemption regardless of age.

### 1.3 Standard deduction (Section 16(ia))

| Regime | Amount |
|---|---|
| New | ₹75,000 |
| Old | ₹50,000 |

Applies to salary and pension income only, capped at the salary amount. Family pension gets a separate deduction: ₹25,000 (new regime) or ₹15,000 / one-third of pension, whichever is lower (old regime).

### 1.4 Rebate under Section 87A

| Regime | Eligibility | Max rebate |
|---|---|---|
| New | Resident individual, total income ≤ ₹12,00,000 | ₹60,000 |
| Old | Resident individual, total income ≤ ₹5,00,000 | ₹12,500 |

Three rules the engine must encode and most calculators get wrong:

1. **Residents only.** An NRI gets no 87A rebate in either regime.
2. **Not on special-rate income.** Under the new regime the rebate is computed on tax charged at slab rates only. Tax on LTCG u/s 112A and (per the Finance Act 2025 position) other special-rate incomes is excluded from the rebate base. Under the old regime the rebate is not available against 112A LTCG.
3. **Marginal relief exists for the rebate cliff.** Under the new regime, if total income exceeds ₹12,00,000, tax payable is capped at `total_income - 12,00,000` until normal tax falls below that. Breakeven is at ₹12,70,588 (`60,000 / 0.85`); beyond that normal tax applies.

### 1.5 Surcharge and surcharge marginal relief

Surcharge is a percentage **of income tax**, keyed off **total income**.

| Total income | Old regime | New regime |
|---|---|---|
| ≤ ₹50,00,000 | Nil | Nil |
| ₹50L - ₹1 crore | 10% | 10% |
| ₹1 crore - ₹2 crore | 15% | 15% |
| ₹2 crore - ₹5 crore | 25% | 25% |
| Above ₹5 crore | 37% | 25% (capped) |

Two caps to implement:

- **15% cap on special-rate slices.** Surcharge on tax attributable to 111A STCG, 112A LTCG, 112 LTCG and dividend income never exceeds 15%, even when the taxpayer's overall rate is 25% or 37%. Split the tax into "normal slice" and "special slice" and surcharge each at its own rate.
- **Marginal relief at every threshold.** Total tax plus surcharge must never increase by more than the income increase that crossed the threshold. Implement as: `if (tax + surcharge) - tax_at_threshold > (income - threshold): surcharge = tax_at_threshold + (income - threshold) - tax`.

### 1.6 Health and education cess

**4%** on (income tax + surcharge, after rebate and marginal relief). Applies in both regimes, to everybody, with no threshold.

### 1.7 Rounding (Section 288A / 288B)

- Total income: round to the nearest ₹10.
- Tax payable and refund: round to the nearest ₹10.
Use `Decimal` with `ROUND_HALF_UP`. Never floats. The US repo already uses `Decimal` throughout; keep that discipline.

### 1.8 The five heads of income

The calculator must compute each head separately before aggregating. This is the biggest structural change from the 1040's flat "total income" line.

**1. Salaries (Sections 15-17)**
```
Gross salary (basic + DA + bonus + allowances + perquisites u/s 17(2) + profits in lieu)
  less exempt allowances u/s 10 (OLD REGIME ONLY: HRA 10(13A), LTA 10(5), children education,
       hostel, transport for disabled, and most 10(14) special allowances)
  less standard deduction u/s 16(ia)
  less entertainment allowance u/s 16(ii) (government employees, old regime)
  less professional tax u/s 16(iii) (OLD REGIME ONLY, state-capped at ₹2,500)
= Income from Salaries
```

**HRA exemption u/s 10(13A) is the least of three:**
1. Actual HRA received
2. 50% of (basic + DA) for Delhi, Mumbai, Kolkata, Chennai; 40% elsewhere
3. Rent paid minus 10% of (basic + DA)

Computed month-wise if salary or rent changed mid-year. Landlord PAN is mandatory if annual rent exceeds ₹1,00,000. The whole exemption is **zero under the new regime**.

**2. House property (Sections 22-27)**
```
Gross annual value (nil for self-occupied, actual/expected rent for let-out)
  less municipal taxes actually paid by the owner
= Net annual value
  less 30% standard deduction u/s 24(a)
  less interest on borrowed capital u/s 24(b)
= Income from House Property
```
Self-occupied: GAV = nil, so the head produces a **loss** equal to the interest, capped at ₹2,00,000. Up to two houses may be treated as self-occupied.
Let-out: full interest is deductible with no cap, but the **loss set off against other heads in the same year is capped at ₹2,00,000** (Section 71(3A)); the balance carries forward 8 years against house-property income only.
**Under the new regime**, self-occupied 24(b) interest is not allowed at all; interest on a let-out property is allowed but the resulting loss cannot be set off against other heads.

**3. Profits and gains of business or profession**
For the scope of this project, support presumptive taxation only:
- **44AD**: 8% of turnover, or **6%** for receipts through banking/digital channels. Turnover limit ₹2 crore, raised to ₹3 crore if cash receipts ≤ 5%.
- **44ADA**: 50% of gross receipts for specified professionals. Limit ₹50 lakh, raised to ₹75 lakh if cash receipts ≤ 5%.
- **44AE**: ₹1,000 per ton of gross vehicle weight per month for heavy goods vehicles, ₹7,500 per month otherwise.
Full books-of-account business income (ITR-3 with balance sheet and P&L) is explicitly **out of scope** - say so in the README rather than half-implementing it.

**4. Capital gains (Sections 45-55, 111A, 112, 112A)**

Post 23 July 2024 regime, FY 2025-26:

| Asset | Holding period for LTCG | LTCG rate | STCG rate |
|---|---|---|---|
| Listed equity shares, equity MF, business trust units (STT paid) | > 12 months | **12.5%** u/s 112A, first **₹1,25,000** per year exempt | **20%** u/s 111A |
| Immovable property | > 24 months | **12.5%** without indexation u/s 112 | Slab rate |
| Unlisted shares, gold, other capital assets | > 24 months | **12.5%** without indexation | Slab rate |
| Specified debt mutual funds, market-linked debentures (u/s 50AA) | n/a | Always treated as STCG | Slab rate |

**Indexation option:** for immovable property **acquired before 23 July 2024** and transferred on or after that date, a resident individual or HUF may choose the lower of 12.5% without indexation or 20% with indexation. CII for FY 2025-26 is **376**. Implement both and take the minimum - that alone is a differentiating feature versus the free calculators.

**Basic exemption adjustment:** a resident whose other income is below the basic exemption limit may set the shortfall against 111A/112A/112 gains. Non-residents may not.

**5. Income from other sources (Sections 56-59)**
Savings bank interest, FD/RD interest, dividends (taxable at slab since FY 2020-21, TDS u/s 194 at 10% above ₹10,000), family pension, gifts above ₹50,000 from non-relatives, interest on income-tax refund, winnings (Section 115BB, flat 30%, no deductions, no 87A).

### 1.9 Set-off and carry-forward rules to encode

| Loss | Intra-head set-off | Inter-head set-off | Carry forward |
|---|---|---|---|
| House property | Yes | Yes, capped at ₹2,00,000/year | 8 years, vs HP income only |
| Short-term capital loss | Against STCG and LTCG | No | 8 years |
| Long-term capital loss | Against LTCG only | No | 8 years |
| Speculative business | Speculative only | No | 4 years |
| Non-speculative business | Yes | Yes (not against salary) | 8 years |
Carry-forward requires the return to be filed **on or before the due date u/s 139(1)**. Losses cannot be carried forward from a belated return (house-property loss excepted).

### 1.10 Chapter VI-A deduction catalogue

| Section | What | Limit FY 2025-26 | New regime? |
|---|---|---|---|
| 80C | LIC, PPF, EPF, ELSS, NSC, 5-yr FD, tuition fees, home-loan principal, Sukanya Samriddhi | ₹1,50,000 (shared with 80CCC, 80CCD(1)) | **No** |
| 80CCC | Pension fund annuity premium | within the ₹1.5L ceiling | No |
| 80CCD(1) | Employee NPS contribution | 10% of salary (20% for self-employed), within ₹1.5L | No |
| 80CCD(1B) | Additional NPS | ₹50,000 over and above 80C | **No** |
| 80CCD(2) | **Employer** NPS contribution | 14% of salary (new regime and government employees), 10% (old regime, private) | **Yes** |
| 80CCH | Agniveer Corpus Fund | Full contribution | **Yes** |
| 80D | Health insurance: self/family ₹25,000 (₹50,000 if senior), parents ₹25,000 (₹50,000 if senior); preventive check-up ₹5,000 within the limit | Max ₹1,00,000 | No |
| 80DD | Maintenance of disabled dependant | ₹75,000 / ₹1,25,000 (severe) | No |
| 80DDB | Treatment of specified diseases | ₹40,000 / ₹1,00,000 (senior) | No |
| 80E | Education loan interest | No cap, 8 years | No |
| 80EE / 80EEA | First-time home-buyer interest | ₹50,000 / ₹1,50,000 | No |
| 80G | Donations | 50% or 100%, some with a 10%-of-adjusted-GTI qualifying cap; cash donations above ₹2,000 disallowed | No |
| 80GG | Rent paid when no HRA | Least of ₹5,000/month, 25% of adjusted total income, rent minus 10% of ATI | No |
| 80GGC | Political party contributions | Full, non-cash only | No |
| 80TTA | Savings bank interest (below 60) | ₹10,000 | No |
| 80TTB | Interest income (senior citizens) | ₹50,000 | No |
| 80U | Disability of the assessee | ₹75,000 / ₹1,25,000 (severe) | No |
| 80JJAA | Additional employee cost | 30% for 3 years | **Yes** |
| Std. deduction 16(ia) | Salary/pension | ₹75,000 new / ₹50,000 old | Yes (both, different amounts) |
| 57(iia) | Family pension | ₹25,000 new / ₹15,000 old | Yes (both) |

**Chapter VI-A deductions can never create or increase a loss** and are not allowed against 111A/112A/112 special-rate incomes.

### 1.11 Prepaid taxes, interest and fees

**Advance tax instalments** (liability ≥ ₹10,000 after TDS; resident seniors with no business income are exempt):

| Due date | Cumulative % | 234C safe harbour |
|---|---|---|
| 15 June | 15% | no interest if ≥ 12% paid |
| 15 September | 45% | no interest if ≥ 36% paid |
| 15 December | 75% | - |
| 15 March | 100% | - |

Presumptive taxpayers (44AD / 44ADA) pay 100% by 15 March in one instalment.

| Provision | Rate / amount | Trigger |
|---|---|---|
| 234A | 1% per month or part | Return filed after the 139(1) due date, on unpaid tax |
| 234B | 1% per month or part | Advance tax paid < 90% of assessed tax, from 1 April of the AY |
| 234C | 1% per month or part | Shortfall in an instalment; 3 months for the first three, 1 month for the last |
| 234F | ₹5,000 (₹1,000 if total income ≤ ₹5,00,000) | Belated return |
| 244A | 0.5% per month (6% p.a.) | Refund interest, from 1 April of the AY (or filing date if belated) to refund; not paid if refund < 10% of tax determined; **taxable in the year of receipt** |

### 1.12 Final tax equation the engine must implement

```
Gross Total Income = Salaries + House Property + Business/Profession + Capital Gains + Other Sources
                     (after intra-head and inter-head set-off)
Total Income       = GTI - Chapter VI-A deductions            [round to nearest ₹10]
Tax at slab rates  = f(normal income portion, regime, age band)
Tax at special rates = 111A@20% + 112A@12.5% (over ₹1.25L) + 112@12.5%/20% + 115BB@30%
Tax before rebate  = slab tax + special tax
less Rebate 87A
= Tax after rebate (apply 87A marginal relief, new regime)
plus Surcharge (rate by total income; 15% cap on special slice; apply surcharge marginal relief)
plus Health & Education Cess @ 4%
= Total tax liability                                          [round to nearest ₹10]
less TDS + TCS + Advance tax + Self-assessment tax + relief u/s 89/90/91
= Refund (if negative) or Tax payable (if positive)
plus Interest u/s 234A / 234B / 234C and fee u/s 234F when applicable
```

### 1.13 ITR form selection decision tree

```
Has business or professional income?
├── No
│   ├── Resident + total income ≤ ₹50L + salary/pension + ≤1 house property
│   │   + other sources + agri ≤ ₹5,000 + LTCG u/s 112A ≤ ₹1,25,000
│   │   + NOT a director + NO unlisted shares + NO foreign asset/income
│   │   + NO STCG + NO loss carry-forward + NO ESOP deferral
│   │   └── ITR-1 (SAHAJ)
│   └── otherwise ────────────────────────────────────────────────── ITR-2
└── Yes
    ├── Presumptive u/s 44AD / 44ADA / 44AE, resident, total income ≤ ₹50L,
    │   and otherwise ITR-1-like ─────────────────────────────────── ITR-4 (SUGAM)
    └── otherwise (books of account, F&O, capital gains + business) ─ ITR-3
```

**Due dates, AY 2026-27:** 31 July 2026 (ITR-1/ITR-2 filers), 31 August 2026 (non-audit business/professional), 31 October 2026 (audit cases), 30 November 2026 (transfer pricing), 31 December 2026 (belated and revised).

### 1.14 Source documents to parse

| Document | Issuer | What the reading agent extracts |
|---|---|---|
| **Form 16 Part A** | Employer via TRACES | TAN, employer name, PAN, quarterly TDS deposited, certificate number, period |
| **Form 16 Part B** | Employer | Gross salary breakup 17(1)/17(2)/17(3), exempt allowances u/s 10, standard deduction, professional tax, Chapter VI-A claimed, taxable income, tax on total income, regime used |
| **Form 12BA** | Employer | Perquisite valuation detail |
| **Form 12BB** | Employee to employer | Declared HRA/LTA/80C evidence |
| **Form 26AS** | TRACES | TDS by deductor and section, advance tax and self-assessment challans, refunds, SFT entries, TCS |
| **AIS** | ITD | Salary, interest, dividends, securities transactions, property purchases, GST turnover; per-entry feedback status |
| **TIS** | ITD | Category-wise aggregated figure derived from AIS after feedback - the number to reconcile against |
| **Broker capital gains statement / P&L** | Zerodha, Groww, ICICI Direct etc. | Scrip-wise buy/sell dates, values, STT flag, realised STCG/LTCG split |
| **Interest certificate** | Bank | FD and savings interest, TDS u/s 194A |
| **Home loan certificate** | Lender | Principal and interest split for 80C and 24(b) |
| **Rent receipts + landlord PAN** | Taxpayer | HRA exemption inputs |
| **Form 10-IEA acknowledgement** | ITD | Regime opt-out status for business-income taxpayers |

**Reconciliation is a first-class verification check:** salary per Form 16 must equal salary per AIS/TIS, and total TDS claimed must equal 26AS. A mismatch is the single most common cause of a defective return notice u/s 139(9), so make the verification agent fail on it rather than warn.

### 1.15 Numbers that must NEVER be hard-coded by an LLM

Slabs, rates, caps, rebate thresholds, surcharge bands, cess, 80C/80D/80CCD limits, capital-gains rates and holding periods, CII values, advance-tax percentages, interest rates, 234F fees. All of them go in `fy_2025_26.py` with `source=` and `verified=`, and are structurally validated by `app/tax_rules/validation.py` (monotonic bands, open top band, rates in (0,1), caps positive). The US repo already has this pattern - copy it exactly.

---
## 2. Target architecture

![India system architecture](india_architecture.png)

*`india_architecture.png` ships alongside this document (3680 x 3056 px, and
`india_architecture.html` is the editable source). Drop it into `docs/architecture.md`.*

### 2.1 Agent roster

| # | Agent | Responsibility | US counterpart |
|---|---|---|---|
| 1 | **Document Reading Agent** | OCR + layout parse of Form 16, 26AS, AIS, broker P&L, certificates; emit `IndianTaxpayerData` with per-field evidence and confidence | `agents/reading` |
| 2 | **Income Computation Agent** | Deterministic five-head computation, set-off, carry-forward, GTI. Regime-neutral facts only | new (split out of tax processing) |
| 3 | **Old Regime Tax Agent** | Chapter VI-A + exemptions + old slabs → full old-regime liability | `agents/tax_processing` (rewritten) |
| 4 | **New Regime Tax Agent** | 115BAC(1A) restricted deductions + new slabs → full new-regime liability | new |
| 5 | **Regime Comparison Agent** | Line-by-line delta, recommendation, breakeven analysis, switching eligibility, what-if on unused 80C headroom | **new, the differentiator** |
| 6 | **Verification Agent** | Two independent verdicts (correctness + completeness), reconciliation vs 26AS/AIS, confidence score, gate at 0.95 | `agents/verification` |
| 7 | **Remediation Agent** | Root-cause the failed check, re-extract at higher DPI or recompute, bounded to N attempts | `agents/remediation` |
| 8 | **Documentation Agent** | Professional comparison PDF + ITR JSON + audit trail + receipt | `agents/documentation` |

Agents 3 and 4 run **in parallel** as two branches of the LangGraph, joining at agent 5. They must consume the **same** `ComputedIncome` object so the comparison is honest; any difference between them has to come from the rule packs, never from a different income figure.

### 2.2 Graph shape

```
START
  └─> parse                 (Document Reading Agent)
        └─> compute_income  (Income Computation Agent)
              ├─> tax_old   (Old Regime Agent)     ─┐  parallel fan-out
              └─> tax_new   (New Regime Agent)     ─┘
                    └─> compare   (Regime Comparison Agent)
                          └─> verify (Verification Agent)
                                ├─ valid ─────────────────> document ─> END
                                ├─ invalid, attempts left ─> remediate ─> parse | compute_income
                                └─ invalid, exhausted ────> manual_review ─> END
```

LangGraph handles the fan-out natively: `graph.add_edge("compute_income", "tax_old")` and `graph.add_edge("compute_income", "tax_new")`, then `graph.add_edge(["tax_old","tax_new"], "compare")`. Keep `MemorySaver` checkpointing keyed on `submission_id` so runs stay resumable and inspectable.

### 2.3 File-by-file migration map

| US path | India path | Action |
|---|---|---|
| `app/schemas/tax.py` | `app/schemas/tax.py` | Rewrite: `W2`→`Form16`, `FilingStatus`→`ResidentialStatus` + `AgeBand`, add `Regime`, `HeadwiseIncome`, `RegimeComparison` |
| `app/tax_rules/federal_2025.py` | `app/tax_rules/fy_2025_26.py` | Rewrite with both regimes' bands |
| `app/tax_rules/federal_2018.py` | `app/tax_rules/fy_2026_27.py` | Second registered year (slabs unchanged, cites Budget 2026) |
| `app/tax_rules/params.py` | `app/tax_rules/params.py` | Extend `TaxYearParams` with `regimes: dict[Regime, RegimeParams]`, `surcharge`, `cess_rate`, `rebate_87a`, `capital_gains`, `chapter_via_limits` |
| `app/tax_rules/validation.py` | same | Keep, extend checks for two regimes and surcharge ordering |
| `app/state_rules/**` (47 packs) | **delete** | India has no state income tax. Delete the package, the registry, the `tenforty` dependency and the state tests. Professional tax u/s 16(iii) is the only state-level item and it is a flat capped deduction, not a tax computation |
| `app/agents/tax_processing/tax_calculator.py` | `app/agents/income/computation.py` + `app/agents/regimes/old_regime.py` + `app/agents/regimes/new_regime.py` | Split three ways |
| - | `app/agents/comparison/agent.py` | New |
| `app/agents/reading/agent.py` | same | Rewrite prompts and field maps for Indian documents |
| `app/services/extraction/w2_parser.py` | `app/services/extraction/form16_parser.py` | Rewrite |
| - | `app/services/extraction/form26as_parser.py`, `ais_parser.py`, `broker_pnl_parser.py` | New |
| `app/services/pdf/form1040.py` | `app/services/pdf/itr_summary.py` | Rewrite (ITR-1/2/4 computation sheet render) |
| `app/services/pdf/professional_report.py` | `app/services/pdf/comparison_report.py` | Rewrite - this is the headline deliverable |
| `app/services/efile/backends.py` | same | `PdfSelfFileBackend`→`JsonSelfFileBackend`, `MockTransmitterBackend`→`MockEriBackend` |
| `app/services/ocr`, `ollama`, `chroma`, `storage` | unchanged | Keep as-is |
| `app/workflow/graph.py`, `state.py` | same | Add three nodes and the fan-out/join |
| `frontend/src/types/tax.ts` | same | Regenerate from the new Pydantic schema |
| `frontend/src/components/AgentPipeline.tsx` | same | Show 8 nodes with the parallel branch |
| - | `frontend/src/components/RegimeComparison.tsx` | New |

### 2.4 Configuration changes (`app/core/config.py`)

```python
app_name: str = "Self-Healing Tax Filing System (India)"
tax_year: str = "2025-26"                 # FY; AY is derived
default_regime: str = "new"               # 115BAC(1A) is the statutory default
verification_threshold: float = 0.95      # keep
max_remediation_attempts: int = 2         # keep
efile_backend: str = "json_self_file"     # "json_self_file" | "mock_eri"
form16_extractor: str = "label"           # "label" (offline) | "azure" (Document Intelligence)
enable_indexation_option: bool = True     # 12.5% vs 20%-with-indexation comparison for property
pan_masking: bool = True                  # mask PAN as ABCxxxxx1F everywhere except the ITR JSON
```

Drop `default_state_tax_rate`, `tenforty`, and every state-related setting.

### 2.5 PAN and Aadhaar handling

The US repo masks SSN as `***-**-1234`. Do the same, harder:

- PAN regex: `^[A-Z]{3}[ABCFGHLJPTK][A-Z][0-9]{4}[A-Z]$`. The 4th character encodes holder type (`P` = individual); validate it, do not just length-check.
- Mask PAN as `ABC****1F` in every log line, API response, PDF body and UI surface. Emit the unmasked PAN **only** into the ITR JSON payload.
- Aadhaar: store the last 4 digits only. Never log the full number. Never put Aadhaar on the PDF.
- Bank account for refund: mask to last 4 plus IFSC. The ITR JSON needs the full number; nothing else does.

---

## 3. Milestones

Each milestone below is written to be pasted into Antigravity as a single task. Work them in order. Every milestone ends with a **Done when** block - do not advance until those pass.

**How to use these:** open the repo in Antigravity, paste the prompt block verbatim, let it plan, review the diff, run the acceptance tests in the Done-when block, commit, move to the next. Prompts assume the working directory is the repo root.

---

### Milestone 0 - Fork, strip, and scaffold

**Goal:** an India-shaped empty skeleton that still boots, with every US-specific module deleted rather than left to rot.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 0

Context: This repo is a US tax filing system (Form 1040) built as a LangGraph multi-agent
pipeline with a FastAPI backend and a React/Vite frontend. I am converting it to an Indian
income tax system for FY 2025-26 (AY 2026-27). Read backend/app/workflow/graph.py,
backend/app/schemas/tax.py, backend/app/agents/tax_processing/tax_calculator.py and
docs/architecture.md first so you understand the existing shape before changing anything.

Do exactly this, nothing more:

1. Delete the entire backend/app/state_rules/ package and every test that imports it
   (tests/unit/test_state_rules.py, test_state_rules_tenforty.py). India has no state
   income tax. Remove `tenforty` from backend/requirements.txt.

2. Delete backend/app/tax_rules/federal_2018.py and federal_2025.py, and
   backend/app/services/extraction/w2_parser.py, info_returns.py, azure_client.py's
   W-2-specific field maps, backend/app/services/pdf/form1040.py, and their tests.
   Leave app/tax_rules/params.py and validation.py in place - I am extending them, not
   replacing them.

3. Rename the app throughout: app_name = "Self-Healing Tax Filing System (India)".
   In backend/app/core/config.py replace the settings block with:
       tax_year: str = "2025-26"
       default_regime: str = "new"
       efile_backend: str = "json_self_file"
       form16_extractor: str = "label"
       enable_indexation_option: bool = True
       pan_masking: bool = True
   and delete default_state_tax_rate, w2_extractor and any state-related setting.

4. Create empty-but-importable packages with __init__.py and a module docstring only:
       backend/app/agents/income/
       backend/app/agents/regimes/
       backend/app/agents/comparison/
       backend/app/services/extraction/india/
       backend/app/itr/           (ITR JSON builders)

5. Create DISCLAIMER.md at the repo root stating that this system prepares and packages
   an income tax return for self-filing at incometax.gov.in, does not transmit returns to
   the Income Tax Department, is not tax advice, and must be reviewed by a qualified
   chartered accountant before filing.

6. Rewrite README.md's architecture section for the Indian pipeline: 8 agents, dual-regime
   parallel branch, self-file-by-default e-filing boundary. Keep the "LLMs read and
   classify, deterministic code decides and computes" principle statement verbatim - it
   is the design invariant of this project.

Constraint: do NOT write any Indian tax logic yet. This milestone is deletion, renaming
and scaffolding only. `python -m pytest backend/tests` must collect without import errors
even though many tests will now be skipped or removed.
```

**Done when:** `pytest backend/tests -q` collects cleanly, `uvicorn app.main:app` boots, `grep -ri "state_rules\|tenforty\|form1040\|w2" backend/app` returns nothing.

---

### Milestone 1 - Schemas: the Indian taxpayer data model

**Goal:** the typed contract every other milestone depends on. Get this wrong and you rewrite everything twice.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 1

Rewrite backend/app/schemas/tax.py for Indian income tax. Follow the existing file's
conventions exactly: Pydantic v2, StrEnum, Decimal for every money field with a
`mode="before"` validator that strips currency symbols and commas, and a `SourceEvidence`
model attached to extracted fields. Keep SourceEvidence, VerificationCheck,
VerificationResult, AuditEntry and SubmissionResult structurally unchanged.

Define these enums:
  Regime            = OLD | NEW
  ResidentialStatus = RESIDENT_ORDINARY | RESIDENT_NOT_ORDINARY | NON_RESIDENT
  AgeBand           = BELOW_60 | SENIOR_60_80 | SUPER_SENIOR_80_PLUS
  ITRForm           = ITR1 | ITR2 | ITR3 | ITR4
  WorkflowStatus    = UPLOADED | PARSING | COMPUTING_INCOME | CALCULATING_OLD |
                      CALCULATING_NEW | COMPARING | VERIFYING | REMEDIATING |
                      COMPLETED | MANUAL_REVIEW | FAILED

Define these models:

Form16(BaseModel)
  employer_name, employer_tan, employer_pan, certificate_number, period_from, period_to
  gross_salary_17_1, perquisites_17_2, profits_in_lieu_17_3
  exempt_allowances_10: dict[str, Decimal]      # {"hra": ..., "lta": ..., ...}
  standard_deduction, professional_tax, entertainment_allowance
  chapter_via_claimed: dict[str, Decimal]       # {"80C": ..., "80D": ...}
  regime_used: Regime
  tds_deducted, taxable_salary_per_employer

SalaryBreakup(BaseModel)     # needed for the HRA least-of-three
  basic, dearness_allowance, hra_received, lta_received, other_allowances,
  rent_paid_annual, landlord_pan, is_metro: bool, months_in_service: int = 12

HouseProperty(BaseModel)
  is_self_occupied: bool, annual_rent_received, municipal_taxes_paid,
  interest_on_loan_24b, principal_repaid_80c, is_let_out: bool, co_owner_share: Decimal = 1

CapitalGainItem(BaseModel)
  asset_type: Literal["listed_equity","equity_mf","immovable_property","unlisted_shares",
                      "gold","debt_mf","other"]
  acquisition_date, transfer_date, cost_of_acquisition, cost_of_improvement,
  transfer_expenses, sale_consideration, stt_paid: bool, is_pre_23jul2024: bool
  # derived, never extracted: holding_days, is_long_term, indexed_cost, gain

PresumptiveBusiness(BaseModel)
  section: Literal["44AD","44ADA","44AE"], turnover, digital_receipts, cash_receipts,
  declared_profit, vehicles: list[dict] | None

TaxesPaid(BaseModel)
  tds_salary, tds_non_salary, tcs, advance_tax_instalments: dict[str, Decimal],
  self_assessment_tax, relief_89, relief_90_91

IndianTaxpayerData(BaseModel)
  # identity
  name, pan, aadhaar_last4, date_of_birth: date | None, residential_status, age_band
  email, mobile, address, bank_account_last4, bank_ifsc
  assessment_year: str = "2026-27", financial_year: str = "2025-26"
  # facts by head
  form16s: list[Form16], salary_breakup: SalaryBreakup | None
  house_properties: list[HouseProperty]
  capital_gains: list[CapitalGainItem]
  presumptive: PresumptiveBusiness | None
  savings_interest, fd_interest, dividend_income, family_pension, other_income,
  winnings_115bb, exempt_income, agricultural_income
  # deduction claims (raw claims; the engine applies caps and regime eligibility)
  deduction_claims: dict[str, Decimal]   # {"80C": 150000, "80D": 25000, "80CCD1B": 50000,
                                         #  "80CCD2": 90000, "80TTA": 10000, "80G": ...}
  taxes_paid: TaxesPaid
  brought_forward_losses: dict[str, Decimal]
  # provenance
  evidence: list[SourceEvidence]
  field_confidence: dict[str, float]

  @property masked_pan  -> "ABC****1F"
  def aggregate_form16s() -> None   # fold multiple employers into salary totals,
                                    # exactly like the existing aggregate_w2s()

HeadwiseIncome(BaseModel)     # regime-NEUTRAL where possible, regime-specific where forced
  regime: Regime
  gross_salary, exempt_allowances, standard_deduction, professional_tax, income_from_salary
  house_property_income  (may be negative), hp_loss_set_off, hp_loss_carried_forward
  business_income
  stcg_111a, stcg_slab, ltcg_112a_gross, ltcg_112a_exempt, ltcg_112a_taxable,
  ltcg_112, capital_gains_total
  other_sources_income
  gross_total_income
  chapter_via: dict[str, Decimal], chapter_via_total
  total_income                       # rounded to nearest 10

RegimeTaxResult(BaseModel)
  regime, income: HeadwiseIncome
  tax_on_slab_income, tax_on_special_income, tax_before_rebate
  rebate_87a, marginal_relief_87a, tax_after_rebate
  surcharge, surcharge_marginal_relief, cess, total_tax_liability
  taxes_paid_total, interest_234a, interest_234b, interest_234c, fee_234f
  refund_due, tax_payable, effective_tax_rate: Decimal
  trace: list[str]                   # every line the engine wrote, for the audit PDF

RegimeComparison(BaseModel)
  old: RegimeTaxResult, new: RegimeTaxResult
  recommended: Regime, savings: Decimal, savings_pct: Decimal
  deltas: list[dict]                 # [{"line": "Standard deduction", "old": .., "new": ..,
                                     #   "delta": ..}] for the comparison table
  deductions_forfeited_if_new: dict[str, Decimal]
  breakeven_deduction_amount: Decimal   # total old-regime deductions at which the two are equal
  unused_80c_headroom: Decimal
  switch_allowed_annually: bool         # False if the taxpayer has business income
  form_10iea_required: bool
  reasons: list[str]                    # plain-English bullets for the PDF recommendation box

Also write backend/app/schemas/validators.py with:
  validate_pan(pan) -> bool           # regex ^[A-Z]{3}[ABCFGHLJPTK][A-Z][0-9]{4}[A-Z]$,
                                      # 4th char must be 'P' for an individual
  mask_pan(pan) -> str
  validate_ifsc(code) -> bool         # ^[A-Z]{4}0[A-Z0-9]{6}$
  age_band_from_dob(dob, fy_end) -> AgeBand

Write unit tests in backend/tests/unit/test_schemas_india.py covering: PAN validation
accepts ABCPD1234E and rejects ABCXD1234E and ABCP1234E; masking; Decimal coercion from
"₹1,50,000" and "1,50,000.00"; age band boundaries at exactly 60 and 80 on 31 March 2026.
```

**Done when:** `pytest backend/tests/unit/test_schemas_india.py -q` is green and `mypy backend/app/schemas` is clean.

---

### Milestone 2 - Versioned tax parameter packs

**Goal:** every Indian tax constant in one auditable file with a citation, validated structurally.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 2

Extend backend/app/tax_rules/params.py and create backend/app/tax_rules/fy_2025_26.py.
Follow the exact pattern of the deleted federal_2025.py: frozen dataclasses, a module
docstring listing statutory sources, a `register()` call, and `verified=True/False` on the
param object. Every constant carries provenance. No constant is computed at runtime.

In params.py add:

@dataclass(frozen=True) class RegimeParams:
    slabs: dict[AgeBand, list[tuple[Decimal|None, Decimal]]]   # (upper_bound, rate), open top
    standard_deduction: Decimal
    family_pension_deduction: Decimal
    rebate_limit: Decimal            # total income ceiling for 87A
    rebate_max: Decimal
    rebate_marginal_relief: bool
    allowed_chapter_via: frozenset[str]
    allows_hra: bool
    allows_lta: bool
    allows_professional_tax: bool
    allows_sop_interest_24b: bool
    allows_hp_loss_setoff: bool
    employer_nps_limit_pct: Decimal  # 0.14 new, 0.10 old (private employees)

@dataclass(frozen=True) class SurchargeParams:
    bands: list[tuple[Decimal|None, Decimal]]   # (total income upper, rate)
    special_income_cap: Decimal                 # 0.15
    marginal_relief: bool = True

@dataclass(frozen=True) class CapitalGainParams:
    stcg_111a_rate, ltcg_112a_rate, ltcg_112a_exemption, ltcg_112_rate,
    ltcg_112_indexed_rate, winnings_115bb_rate
    holding_months: dict[str, int]              # {"listed_equity": 12, "immovable": 24, ...}
    cii: dict[int, int]                         # FY -> Cost Inflation Index
    indexation_option_cutoff: date              # 2024-07-23

@dataclass(frozen=True) class ChapterVIALimits:
    limits: dict[str, Decimal]                  # {"80C": 150000, "80CCD1B": 50000, ...}
    senior_variants: dict[str, Decimal]         # {"80D": 50000, "80TTB": 50000, "80DDB": 100000}
    combined_ceilings: dict[str, tuple[str,...]] # {"80C": ("80C","80CCC","80CCD1")}

@dataclass(frozen=True) class InterestParams:
    rate_234a, rate_234b, rate_234c: Decimal    # all 0.01 per month
    fee_234f_high, fee_234f_low, fee_234f_income_threshold
    refund_interest_244a: Decimal               # 0.005 per month
    advance_tax_schedule: list[tuple[str, Decimal, Decimal]]  # (due date, cumulative %, safe %)
    advance_tax_threshold: Decimal              # 10000

Extend TaxYearParams with: financial_year: str, assessment_year: str,
regimes: dict[Regime, RegimeParams], surcharge: dict[Regime, SurchargeParams],
cess_rate: Decimal, capital_gains: CapitalGainParams, chapter_via: ChapterVIALimits,
interest: InterestParams, source: str, verified: bool.

Then populate fy_2025_26.py with the values in the rulebook section of
INDIA_TAX_MIGRATION.md sections 1.1 to 1.11. Cite: Finance Act 2025; Section 115BAC(1A);
Sections 87A, 111A, 112, 112A, 115BB; Sections 234A/B/C/F and 244A; Chapter VI-A.
Set verified=True only for the slab tables, standard deduction, 87A, surcharge, cess and
capital-gains rates; set verified=False on the CII table and the 80G qualifying-limit
logic until a maintainer checks them against the notified figures.

Create fy_2026_27.py as a copy with financial_year="2026-27", assessment_year="2027-28",
source citing Budget 2026 (slabs unchanged), and a module docstring noting that from
1 April 2026 the Income-tax Act 2025 replaces the 1961 Act: same rates, renumbered
sections (115BAC -> 202, 80C -> 123, 192 -> 392, 139 -> 263), and "tax year" replaces
"previous year / assessment year". Add a `section_map: dict[str,str]` to that module so
the PDF can print the correct section labels per year.

Extend backend/app/tax_rules/validation.py with structural checks:
 - every slab list ends with an open (None, rate) band
 - slab upper bounds strictly increasing, rates non-decreasing
 - new-regime top rate == old-regime top rate == 0.30
 - surcharge bands ordered and rates increasing; new-regime max rate <= old-regime max rate
 - 0 < cess_rate < 1; rebate_max > 0; rebate_limit > rebate_max
 - allowed_chapter_via for NEW is a strict subset of the OLD set, and contains 80CCD2
 - every key in ChapterVIALimits.limits is a known section string
Run validate_all() over the registry in a test that fails the build on any issue.

Write backend/tests/unit/test_params_india.py asserting: slab tax on ₹10,00,000 under the
new regime is ₹50,000 before cess; under the old regime (below 60) it is ₹1,12,500;
old-regime senior slab tax on ₹10,00,000 is ₹1,10,000; validate_all() returns [].
```

**Done when:** `pytest backend/tests/unit/test_params_india.py -q` is green and `validate_all()` returns an empty list for both registered years.

---

### Milestone 3 - Income Computation Agent (the five heads)

**Goal:** regime-neutral facts turned into head-wise income, with the regime-specific switches passed in rather than hard-coded.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 3

Create backend/app/agents/income/computation.py with a deterministic
IncomeComputationService. Signature:

    def compute(data: IndianTaxpayerData, regime: Regime, params: TaxYearParams)
        -> HeadwiseIncome

No LLM calls anywhere in this file. Every branch appends a human-readable line to a trace
list that ends up in HeadwiseIncome, e.g. "Salary: gross 15,00,000 less HRA exemption
2,00,000 (least of 2,40,000 / 3,60,000 / 2,00,000) less standard deduction 50,000".

Implement, in this order:

1. SALARIES
   gross = sum over form16s of (17(1) + 17(2) + 17(3))
   if regime is OLD: subtract exempt allowances u/s 10. Compute HRA with a dedicated
     function hra_exemption(salary_breakup, params) that returns the least of:
       (a) actual HRA received
       (b) 50% of (basic+DA) if is_metro else 40%
       (c) rent paid minus 10% of (basic+DA), floored at 0
     Return 0 if rent_paid is 0. Warn (do not fail) if rent > 100000 and landlord_pan is
     empty - that becomes a verification check later.
   if regime is NEW: exempt allowances = 0 except the 10(14) items that survive
     (conveyance for the disabled, tour/transfer allowance, daily allowance).
   subtract standard deduction = min(params.regimes[regime].standard_deduction, gross)
   subtract professional tax (OLD only, cap 2500) and entertainment allowance (OLD,
     government employees only, least of 5000 / 20% of basic / actual).

2. HOUSE PROPERTY - per property, then summed
   self-occupied: GAV = 0; interest u/s 24(b) allowed only in OLD, capped at 200000
     across all self-occupied properties combined; result is a loss.
   let-out: GAV = annual rent received; less municipal taxes paid; NAV; less 30% of NAV
     u/s 24(a); less full interest u/s 24(b) (allowed in BOTH regimes).
   apply co_owner_share.
   Inter-head set-off of the net HP loss: OLD regime caps the set-off at 200000 per year
     (Section 71(3A)) and carries the remainder forward 8 years. NEW regime does not permit
     any HP loss to be set off against other heads; the whole loss carries forward.
   Record hp_loss_set_off and hp_loss_carried_forward separately - the PDF shows both.

3. BUSINESS/PROFESSION (presumptive only)
   44AD: profit = max(declared_profit, 0.06*digital_receipts + 0.08*cash_receipts).
         Reject with a clear error if turnover > 3_00_00_000, or > 2_00_00_000 when
         cash_receipts > 5% of turnover.
   44ADA: profit = max(declared_profit, 0.50*gross_receipts). Limit 50_00_000, or
         75_00_000 when cash receipts <= 5%.
   44AE: 1000 per ton per month for vehicles > 12T GVW, else 7500 per vehicle per month.
   Identical in both regimes.

4. CAPITAL GAINS - per CapitalGainItem
   holding period from params.capital_gains.holding_months by asset_type; classify
     long/short. Debt MF and MLDs u/s 50AA are ALWAYS short-term at slab rates.
   gain = sale_consideration - transfer_expenses - cost_of_acquisition - cost_of_improvement
   listed equity/equity MF with stt_paid:
     short -> stcg_111a bucket (20%)
     long  -> ltcg_112a bucket; aggregate across items, exempt the first 1,25,000,
              remainder is ltcg_112a_taxable (12.5%)
   immovable property / unlisted / gold:
     short -> stcg_slab bucket (taxed at slab, added to normal income)
     long  -> ltcg_112 bucket at 12.5% without indexation; if is_pre_23jul2024 and the
              taxpayer is a resident individual/HUF and settings.enable_indexation_option,
              ALSO compute 20% on the indexed gain using CII, and take the LOWER tax.
              Record which option won in the trace.
   Intra-head set-off: STCL against STCG then LTCG; LTCL against LTCG only. Apply brought-
     forward losses after current-year set-off. Never set capital losses against other heads.
   Basic-exemption adjustment: if the taxpayer is RESIDENT and normal income is below the
     basic exemption limit for the regime/age band, absorb the shortfall against special-
     rate gains in the order 112 -> 111A -> 112A (most expensive first is wrong; use this
     statutory-friendly order and document it). Non-residents get no adjustment.

5. OTHER SOURCES
   savings interest + FD interest + dividends + family pension (less the applicable family
   pension deduction) + interest on refund + other. Winnings u/s 115BB stay in their own
   bucket - they are taxed at a flat 30% with no deduction and no 87A.

6. GROSS TOTAL INCOME = sum of the five heads after set-off.

7. CHAPTER VI-A
   Build a function apply_chapter_via(claims, gti, data, regime, params) that:
     - drops any section not in params.regimes[regime].allowed_chapter_via
     - applies per-section caps, senior variants (80D, 80TTB, 80DDB) by age_band
     - applies combined ceilings (80C + 80CCC + 80CCD(1) <= 1,50,000)
     - caps 80CCD(2) at employer_nps_limit_pct * (basic + DA)
     - 80G: apply the 50%/100% rate and the 10%-of-adjusted-GTI qualifying cap where
       applicable; disallow cash donations above 2,000
     - clamps the total so it can never exceed GTI reduced by special-rate income, and
       never creates a loss
   Return the applied dict AND a `disallowed` dict explaining every rejection - the
   comparison PDF prints that list as "deductions you forfeit under the new regime".

8. TOTAL INCOME = GTI - chapter VI-A total, rounded to the nearest ₹10 (Section 288A).

Write backend/tests/unit/test_income_computation.py with at least these cases:
 - HRA least-of-three picks each of the three limbs in three separate tests
 - self-occupied interest of 3,00,000 is capped at 2,00,000 in OLD and 0 in NEW
 - let-out loss of 3,50,000 sets off 2,00,000 and carries 1,50,000 forward in OLD
 - 112A gains of 2,00,000 leave 75,000 taxable after the 1,25,000 exemption
 - property bought in 2015 and sold in 2025 picks whichever of 12.5%/20%-indexed is lower
 - 80C claim of 2,00,000 is capped at 1,50,000 in OLD and dropped entirely in NEW
 - 80CCD(2) survives in both regimes at the correct percentage cap
```

**Done when:** all income tests pass and `HeadwiseIncome.trace` for a sample return reads as a coherent computation sheet a CA could follow line by line.

---
### Milestone 4 - Dual regime tax engines

**Goal:** two calculators that share one income object and differ only by their parameter pack.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 4

Create backend/app/agents/regimes/base.py, old_regime.py and new_regime.py.

base.py holds ALL the shared arithmetic, because the only legal difference between the two
regimes is in the parameter pack, not in the algorithm. Write these pure functions:

  slab_tax(normal_income, slabs) -> Decimal
      exact progressive banding; reuse the existing progressive_tax() helper from
      app/tax_rules/params.py rather than writing a second one.

  special_rate_tax(income: HeadwiseIncome, cg: CapitalGainParams) -> tuple[Decimal, dict]
      stcg_111a * 0.20 + ltcg_112a_taxable * 0.125 + ltcg_112 * (0.125 or the indexed
      20% figure chosen in Milestone 3) + winnings * 0.30.
      Return the total AND a per-section breakdown for the PDF.

  rebate_87a(total_income, slab_tax, special_tax, regime, params, is_resident)
        -> tuple[rebate, marginal_relief]
      Rules: residents only. New regime: total income <= 12,00,000 gives
      min(slab_tax, 60,000); the rebate is NOT computed on special-rate tax. Old regime:
      total income <= 5,00,000 gives min(slab_tax + stcg_111a tax, 12,500), excluding
      112A tax. Marginal relief (new regime only): if total_income > 12,00,000 and
      (tax after rebate) > (total_income - 12,00,000), cap tax at (total_income -
      12,00,000) and record the difference as marginal_relief_87a. Breakeven is
      12,70,588; above it relief is always zero, and a test must assert that.

  surcharge(total_income, tax_after_rebate, special_tax, regime, params)
        -> tuple[surcharge, marginal_relief]
      Look up the band rate by total_income. If the rate exceeds 15%, split: surcharge =
      (tax_after_rebate - special_tax) * band_rate + special_tax * 0.15. Then apply
      marginal relief at the crossed threshold T: compute the total tax+surcharge of a
      taxpayer with exactly income T under the same regime; if
      (tax + surcharge) - tax_at_T > (total_income - T), reduce surcharge so that
      tax + surcharge == tax_at_T + (total_income - T).

  cess(tax_plus_surcharge, rate) -> Decimal

  interest_and_fees(total_tax, taxes_paid, filing_date, due_date, params)
        -> dict with interest_234a, interest_234b, interest_234c, fee_234f
      234A: 1% per month or part on unpaid tax from the day after the due date.
      234B: 1% per month from 1 April of the AY if advance tax paid < 90% of assessed tax.
      234C: per-instalment shortfall against 15/45/75/100% with the 12%/36% safe harbours,
            3 months for the first three instalments and 1 month for the last;
            presumptive taxpayers are tested only against the 15 March 100% instalment.
      234F: 5,000, or 1,000 if total income <= 5,00,000, or 0 if the return is on time or
            income is below the basic exemption and filing was not mandatory.

  round_to_ten(value) -> Decimal      # Section 288A/288B, ROUND_HALF_UP

old_regime.py and new_regime.py each expose:

    class OldRegimeCalculator:      # and NewRegimeCalculator
        def calculate(self, data: IndianTaxpayerData, income: HeadwiseIncome,
                      params: TaxYearParams, filing_date: date) -> RegimeTaxResult

Both are 30-line orchestrations over base.py. If you find yourself writing regime-specific
arithmetic inside either file, stop - that difference belongs in RegimeParams instead.
This is the property the whole comparison rests on: the two regimes must be the same
algorithm with different constants, or the comparison is not apples to apples.

Each calculator appends every step to RegimeTaxResult.trace in the form
"Tax on slab income 13,50,000 = 82,500" so the PDF audit appendix is a literal transcript.

Write backend/tests/unit/test_regime_engines.py with the golden vectors in section 5 of
INDIA_TAX_MIGRATION.md. Every expected number in that table is hand-verified; if your
implementation disagrees with the table, your implementation is wrong. Use
pytest.mark.parametrize over the table.
```

**Done when:** every golden vector in section 5 passes to the rupee.

---

### Milestone 5 - Regime Comparison Agent

**Goal:** the feature that makes this an Indian product and not a translated American one.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 5

Create backend/app/agents/comparison/agent.py.

    class RegimeComparisonAgent:
        def run(self, data: IndianTaxpayerData, old: RegimeTaxResult,
                new: RegimeTaxResult) -> tuple[RegimeComparison, AuditEntry]

This agent is deterministic. It does arithmetic and applies documented rules; it does not
call an LLM. (An optional LLM pass may rewrite `reasons` into friendlier prose, behind a
settings flag, but it must never alter a number.)

Produce:

1. recommended = the regime with the lower total_tax_liability. Tie-break to NEW, because
   it is the statutory default and needs no Form 10-IEA.

2. savings = abs(old.total_tax_liability - new.total_tax_liability)
   savings_pct = savings / max(old, new) * 100

3. deltas: an ordered list of comparison rows, one per line of the computation, each with
   {line, old_value, new_value, delta, note}. The order must be the order a CA reads a
   computation sheet:
       Gross salary / Exempt allowances (HRA, LTA) / Standard deduction /
       Professional tax / Income from salary / House property income or loss /
       Business income / Capital gains (each special-rate bucket separately) /
       Income from other sources / Gross total income /
       each Chapter VI-A section claimed, one row each /
       Total Chapter VI-A / Total income / Tax at slab rates / Tax at special rates /
       Rebate u/s 87A / Marginal relief / Surcharge / Health & education cess /
       Total tax liability / Taxes already paid / Refund or Tax payable

4. deductions_forfeited_if_new: every Chapter VI-A section and exemption the taxpayer
   actually claimed that the new regime disallows, with its rupee value and the tax value
   of losing it at the taxpayer's old-regime marginal rate. This is the single most useful
   table in the report.

5. breakeven_deduction_amount: solve for the total old-regime deduction D at which
   old-regime tax equals new-regime tax, holding gross income constant. Compute it
   numerically with a bisection over D in [0, gross_total_income] to a rupee, using the
   real engines rather than a closed-form approximation, so it stays correct across
   slab boundaries, surcharge thresholds and the 87A cliff. Phrase it in the report as:
   "The old regime becomes cheaper for you once your total deductions and exemptions
   exceed ₹X. You currently claim ₹Y."

6. unused_80c_headroom = 1,50,000 minus the 80C+80CCC+80CCD(1) actually claimed, and the
   same for 80CCD(1B) and 80D. Only meaningful when the old regime is recommended or
   within ₹25,000 of winning; suppress the section otherwise so the report does not
   nudge someone into a pointless investment.

7. switch_allowed_annually = False if data.presumptive is not None or business income > 0,
   else True.
   form_10iea_required = True when the recommended regime is OLD and the taxpayer has
   business/professional income. Include the due-date warning: Form 10-IEA must be filed
   on or before the 139(1) due date or it is treated as invalid.

8. reasons: 3 to 5 plain-English bullets explaining the recommendation, generated from
   rules, not prose templates picked at random. Examples of the shapes to emit:
     "Your HRA exemption of ₹2,00,000 and Section 24(b) interest of ₹2,00,000 are worth
      ₹1,24,800 in tax under the old regime and nothing under the new regime."
     "Even with zero deductions the new regime's ₹60,000 rebate wipes out your entire
      liability, so no investment can make the old regime cheaper for you."
     "The two regimes are within ₹3,200 of each other. Choose the new regime for the
      lighter compliance unless you expect your 80C investments to rise next year."

Also add a what-if helper used by the PDF and the UI:

    def sensitivity(self, data, params, deduction_deltas: list[Decimal]) -> list[dict]
        # re-run the old-regime engine at GTI-constant, deduction = current + delta for
        # each delta in the list, returning [{delta, old_tax, new_tax, winner}]
        # Default deltas: -50000, -25000, 0, +25000, +50000, +100000, +150000

Wire the agent into backend/app/workflow/graph.py:
  - add nodes "compute_income", "tax_old", "tax_new", "compare"
  - edges: parse -> compute_income; compute_income -> tax_old; compute_income -> tax_new;
    [tax_old, tax_new] -> compare; compare -> verify
  - extend TaxWorkflowState with computed_income_old, computed_income_new, result_old,
    result_new, comparison
  - keep the existing conditional routing out of verify untouched

Write backend/tests/unit/test_comparison.py: a taxpayer with 3,25,000 of old-regime
deductions on a ₹15,00,000 salary must be recommended OLD with savings of ₹23,380
(golden case 1); a taxpayer with ₹12,00,000 salary and ₹50,000 of 80C must be recommended
NEW with the old-regime tax at ₹1,48,200 and the new-regime tax at ₹0 (golden case 2);
breakeven must be monotonic and must reproduce the crossover when fed back into the
engines.
```

**Done when:** golden cases 1 and 2 return the expected recommendation, savings and breakeven, and the LangGraph run visits all eight nodes in the right order.

---

### Milestone 6 - Document Reading Agent for Indian documents

**Goal:** the messy part. Real Form 16s are two-page PDFs with wildly varying layouts; 26AS and AIS are machine-generated and far more regular.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 6

Rewrite backend/app/agents/reading/agent.py and add parsers under
backend/app/services/extraction/india/.

Keep the existing architecture exactly: PyMuPDF renders each page at a scale that
INCREASES on each remediation pass (the current code uses scale = 2 + reextraction_passes;
keep that), Tesseract OCR as the offline path, a vision LLM for layout understanding, an
optional Azure Document Intelligence cloud path behind a settings flag, per-field
confidence scores, and SourceEvidence recording page number and raw matched text for
every extracted figure.

Write these parsers, each with the signature parse(text: str, page_images) -> (model, evidence):

1. form16_parser.py
   Part A anchors: "TAN of the Deductor", "PAN of the Deductee", "Certificate Number",
   "Assessment Year", "Period with the Employer", "Amount of tax deposited/remitted".
   Part B anchors: "Gross Salary", "(a) Salary as per provisions contained in section
   17(1)", "(b) Value of perquisites under section 17(2)", "Less: Allowances to the extent
   exempt under section 10", "Total amount of exemption claimed under section 10",
   "Less: Deductions under section 16", "(a) Standard deduction under section 16(ia)",
   "(c) Tax on employment under section 16(iii)", "Income chargeable under the head
   'Salaries'", "Deductions under Chapter VI-A", "Total taxable income",
   "Tax payable", "Relief under section 89".
   The Part B annexure lists 80C/80CCC/80CCD with both "Gross Amount" and "Deductible
   Amount" columns - ALWAYS take the deductible amount, and record in the trace that you
   did. Detect the regime the employer used: Form 16 for the new regime shows a nil or
   tiny Chapter VI-A block and a ₹75,000 standard deduction.
   Handle multiple Form 16s (job change): parse each, keep them as separate list entries,
   and flag overlapping employment periods for verification, because double-counting the
   basic exemption across two employers is the classic error the system should catch.

2. form26as_parser.py
   Sections: Part I (TDS from salary, by TAN), Part II (TDS from income other than
   salary), Part III (TDS u/s 194IA/IB/M), Part IV (TDS on sale of immovable property),
   Part V (transactions in SFT), Part VI (TCS), Part VII (paid refunds), Part VIII
   (advance tax / self-assessment tax challans with BSR code, challan serial and date).
   Output a TaxesPaid object plus a per-deductor TDS ledger keyed by TAN and section.

3. ais_parser.py
   The AIS PDF is password-protected with PAN-in-lowercase + DDMMYYYY date of birth.
   Accept a password parameter and, when a PDF is encrypted, try that construction from
   the already-extracted PAN and DOB before failing with a clear error. Parse the
   information categories: Salary, Interest from savings bank, Interest from deposits,
   Dividend, Sale of securities and units of mutual fund, Purchase of immovable property,
   GST turnover, Off-market transactions. Each row has Information Source, Value, and a
   feedback status - carry the status through, because "Information is duplicate" changes
   how a mismatch should be treated.

4. broker_pnl_parser.py
   Support the Zerodha Console, Groww and generic CSV/XLSX tax P&L layouts. Required
   columns after normalisation: symbol, isin, quantity, buy_date, buy_value, sell_date,
   sell_value, realised_pnl, and whichever of "short term"/"long term" the file declares.
   Do NOT trust the broker's own long/short classification - recompute holding period from
   the dates and the asset type, and raise a verification warning when your classification
   disagrees with theirs. Map each row to a CapitalGainItem with stt_paid=True for listed
   equity segments.

5. certificate_parsers.py
   Bank interest certificate (savings vs FD split, TDS u/s 194A), home loan provisional
   certificate (principal for 80C and interest for 24(b), plus pre-construction interest
   where shown), LIC/ELSS/PPF receipts, 80D premium receipts, rent receipts (monthly rent,
   landlord name and PAN).

The LLM's contract in this milestone, stated in the system prompt you write for it:
"You are reading an Indian tax document. Return ONLY a JSON object matching the given
schema. Copy numbers exactly as printed. Never compute, never sum, never infer a missing
value, never convert between lakhs and rupees. If a field is absent, return null. For every
field you return, also return the exact substring of the document it came from."

Then add a deterministic post-processor that:
 - strips ₹, commas, and "Rs." and converts lakh/crore words when they appear in prose
 - cross-foots each Form 16: 17(1)+17(2)+17(3) must equal the printed gross salary;
   gross minus exemptions minus section 16 deductions must equal the printed
   "Income chargeable under the head Salaries". Any mismatch lowers field_confidence and
   is recorded as an extraction issue rather than silently corrected.
 - computes field_confidence per field: 1.0 for a regex/anchor hit with a cross-foot pass,
   0.8 for an anchor hit without cross-foot, the model's own score for a vision-only hit,
   0.4 for an OCR-only numeric guess.

Write backend/tests/unit/test_form16_reading.py using synthetic Form 16 text fixtures
(generate them in backend/app/synthetic/ the way the existing generator.py does for W-2s -
extend that module to emit Form 16 Part A/B, a 26AS extract and a Zerodha P&L CSV).
Assert: a new-regime Form 16 is detected as NEW; a two-employer case produces two Form16
objects and an overlap flag; the cross-foot failure path lowers confidence instead of
throwing.
```

**Done when:** synthetic Form 16 PDFs round-trip into `IndianTaxpayerData` with every field carrying evidence, and a deliberately corrupted fixture lowers confidence rather than crashing.

---

### Milestone 7 - Verification Agent, Indian check pack

**Goal:** two independent verdicts, an honest confidence number, and a hard gate. Keep the existing scoring machinery; replace the checks.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 7

Rewrite backend/app/agents/verification/agent.py and completeness.py for India. Keep the
existing structure: weighted checks, a rule score, an extraction-confidence score,
confidence = 0.8 * rule_score + 0.2 * extraction_confidence, VALID only when correctness
AND completeness both pass AND confidence >= settings.verification_threshold (0.95), and
the same requires_reextraction signal that drives the remediation router.

CORRECTNESS checks (weight in brackets):
 [3] Recomputation: re-run BOTH regime engines from the extracted data in a fresh
     calculator instance and assert both total_tax_liability values match the stored
     results to the rupee. This is the anti-hallucination check and it must be weighted
     highest.
 [3] TDS reconciliation: sum of TDS claimed across Form 16s and certificates equals the
     total in Form 26AS Part I + Part II, within ₹1. A mismatch here is what produces a
     139(9) defective-return notice, so it fails the return rather than warning.
 [2] AIS/TIS reconciliation: salary, interest and dividend totals match AIS within 1% or
     ₹1,000, whichever is larger. Report each mismatched category by name.
 [2] Slab arithmetic: independently recompute slab tax with a second, differently-written
     implementation (a simple loop over cumulative band amounts) and compare.
 [2] Regime comparison sanity: the recommended regime has the lower liability; both
     regimes were computed from the same HeadwiseIncome gross figures; the delta table sums
     to the headline savings figure.
 [2] Deduction legality: no Chapter VI-A section appears in the new-regime result outside
     the allowed set; no section exceeds its cap; 80C + 80CCC + 80CCD(1) <= 1,50,000.
 [2] Capital gains: every item's long/short classification matches the holding period
     computed from its dates; 112A exemption applied exactly once across all items and not
     per item; indexation option only used where legally available.
 [1] Special-rate isolation: 87A rebate was not applied to 112A tax; Chapter VI-A was not
     applied against special-rate income; surcharge on the special slice did not exceed 15%.
 [1] Arithmetic identity: total_income = GTI - chapter_via_total, and
     refund - tax_payable == taxes_paid_total - total_tax_liability.
 [1] Rounding: total income and tax are multiples of 10.
 [1] PAN validity and the 4th-character 'P' check; IFSC format; PAN on Form 16 matches the
     taxpayer PAN.

COMPLETENESS checks:
 [3] Every figure on the return traces to a SourceEvidence entry. Anything without
     evidence is a hallucination flag, exactly as the US completeness.py does it.
 [2] Required documents present for what is being claimed: HRA claimed but no rent receipt;
     24(b) claimed but no loan certificate; capital gains present but no broker statement;
     80C claimed but no proof documents.
 [2] ITR form selection: run the decision tree in section 1.13 and assert the chosen form
     can legally carry every item present. ITR-1 with any STCG, any foreign asset, any
     carried-forward loss, LTCG 112A above ₹1,25,000, or total income above ₹50,00,000 is
     an automatic fail with a specific message naming the disqualifying item.
 [1] Landlord PAN present when annual rent exceeds ₹1,00,000.
 [1] Bank account provided and IFSC valid when a refund is due.
 [1] Form 10-IEA flagged when the old regime is recommended and business income exists.
 [1] Due-date awareness: if the filing date is past the 139(1) due date, 234F and the loss
     carry-forward restriction are applied and surfaced, not silently ignored.

Every failed check must produce a message that names the field, the expected value, the
found value and the document it came from. "Verification failed" with no detail is useless
to the remediation agent.

Write backend/tests/unit/test_verification_india.py: a clean golden return scores >= 0.95
and passes; a return with 80C injected into the new-regime result fails the deduction
legality check; a return whose stored tax is off by ₹100 fails recomputation; a return with
a ₹5,000 TDS mismatch against 26AS fails reconciliation; an ITR-1 selection with STCG
present fails form selection with a message naming STCG.
```

**Done when:** each negative test fails on exactly the check it targets, and the golden return passes with confidence ≥ 0.95.

---

### Milestone 8 - Remediation loop

**Goal:** keep the existing bounded self-healing; teach it Indian failure modes.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 8

Adapt backend/app/agents/remediation/agent.py. Keep the bounded-attempt design and the
router that sends the graph back to either "parse" (when re-extraction is needed) or
"compute_income" (when only recomputation is needed). Do not raise max_remediation_attempts
above 2 - an unbounded self-healing loop is how these systems burn tokens and still fail.

Map each verification failure to a specific remediation action:

 recomputation mismatch      -> recompute only; never re-extract. If it fails twice, the
                                bug is in the engine, so escalate to manual_review with the
                                two differing traces attached side by side.
 TDS mismatch vs 26AS        -> re-extract the 26AS at a higher render scale, then prefer
                                the 26AS figure over the Form 16 figure and record the
                                override in the audit trail with both values.
 AIS mismatch                -> re-extract AIS; if the mismatch survives, do NOT silently
                                adopt either number. Add a "reconciliation required" item
                                to the report, drop confidence, and route to manual_review.
                                Wrong reconciliation is worse than an admitted mismatch.
 cross-foot failure on Form 16 -> re-extract that document only, at scale + 1, and try the
                                cloud extractor if configured
 missing field with evidence gap -> re-extract the specific page that should contain it,
                                using the field's anchor strings as a targeted prompt
 deduction cap breach        -> recompute with the cap applied; log the original claim
 capital gains classification conflict -> recompute from dates; the broker's label loses
 ITR form mismatch           -> re-select the form, no re-extraction

Every remediation writes an AuditEntry with agent, action, reason, the field involved, the
old value, the new value and the attempt number. The PDF's audit appendix renders this as
a table, so a reviewer can see exactly what the system corrected and why. That table is the
"self-healing" claim made auditable, and it is what turns the demo from a calculator into
a system.
```

**Done when:** a fixture with a deliberately corrupted 26AS figure heals in one pass and shows the correction in the audit trail; a fixture with an engine mismatch escalates to manual review instead of looping.

---
### Milestone 9 - The Regime Comparison Advisory Report (PDF)

**Goal:** the deliverable the taxpayer actually holds. It has to look like it came out of a CA firm, not out of a language model.

```
PROMPT FOR ANTIGRAVITY - MILESTONE 9

Replace backend/app/services/pdf/professional_report.py with
backend/app/services/pdf/comparison_report.py. Use ReportLab platypus, A4 portrait,
margins 18mm left/right, 16mm top, 18mm bottom. Read section 4 of INDIA_TAX_MIGRATION.md
before you write a line: it is the full design specification and it is not negotiable.
Non-negotiable items are marked HARD in that section.

Build these helpers first, in backend/app/services/pdf/style.py:

  register_fonts()
      Download nothing at runtime. Vendor the TTFs into backend/assets/fonts/ and register
      a real typeface family with pdfmetrics.registerFont: Source Sans 3 (or Inter) in
      Regular/Semibold/Bold for text, and IBM Plex Mono or Source Sans 3 with tabular
      figures for every numeric column. Fall back to Helvetica ONLY if the TTFs are absent,
      and log a warning when that happens. HARD: default Helvetica everywhere is the single
      biggest tell that a document was machine-assembled without design intent.

  inr(value, decimals=0) -> str
      Indian digit grouping: last three digits, then groups of two.
      1234567.0  -> "12,34,567"
      100000     -> "1,00,000"
      -45300     -> "(45,300)"      # negatives in parentheses, never with a minus sign
      HARD: Western grouping (1,234,567) in an Indian tax document is an immediate
      credibility failure. Write a unit test with at least 12 boundary values including
      0, 999, 1000, 99999, 100000, 9999999, 10000000 and a negative.

  inr_words(value) -> str           # "Rupees Twelve Lakh Thirty Four Thousand only"
      For the refund/payable figure, the way a cheque or an order prints it.

  PALETTE: exactly six colours, no more.
      INK      #10151B   body text
      MUTED    #5B6672   labels, captions, footers
      RULE     #D8DEE5   hairlines
      ACCENT   #0B3D5C   section headers, table headers (a deep navy, not blue-purple)
      POSITIVE #0F7B4F   refund, savings
      NEGATIVE #A8342A   tax payable, forfeited value
      HARD: no gradients, no drop shadows, no rounded "card" containers, no icon glyphs,
      no emoji, no more than one accent colour, no full-width colour blocks except the
      single recommendation banner and the section header bars.

  money_table(rows, col_widths, ...) -> Table
      Numeric columns right-aligned with tabular figures and a consistent 2-decimal or
      0-decimal policy per table (never mixed within a column). Header row: ACCENT
      background, white semibold 8.5pt, 6pt padding. Body: 9pt, 5pt padding. Hairline
      RULE rules below the header and above any total row; a 0.8pt ACCENT rule above the
      grand total. No vertical grid lines. No zebra striping heavier than #F6F8FA, and
      only on tables longer than 12 rows.

  section_header(number, title) -> flowable
      "3. Comparison of tax under both regimes" in 10.5pt semibold white on a 16pt-tall
      ACCENT bar spanning the content width. Numbered sequentially, like a computation
      sheet. HARD: sections are numbered and the numbering is continuous across pages.

  page_furniture(canvas, doc)
      Header on every page after page 1: taxpayer name and masked PAN on the left,
      "Assessment Year 2026-27" on the right, 7.5pt MUTED, hairline rule beneath.
      Footer on every page: "Page X of Y" centred, "Document ID: <uuid8>  ·  Generated
      <DD Mon YYYY HH:MM IST>" left, and on the right the disclaimer
      "Computer-generated advisory. Not tax advice." 7pt MUTED.
      HARD: "Page X of Y" requires a two-pass build - use a canvasmaker that counts pages.

Then build the document with these sections in this exact order:

PAGE 1 - DECISION PAGE (the only page most people will read)
  Masthead: the firm/product name in 16pt semibold, a 1pt ACCENT rule, then
  "Income Tax Computation and Regime Comparison" 13pt, "Assessment Year 2026-27
  (Financial Year 2025-26)" 9.5pt MUTED.
  Identity strip: a 4-column borderless table - Name | PAN (masked) | Status & age band |
  ITR form applicable. 8.5pt, labels in MUTED above values in INK.

  RECOMMENDATION BANNER: full content width, 44pt tall, ACCENT fill, white text.
    Left: "Recommended: OLD REGIME" 14pt semibold.
    Right: "You save ₹23,380" 14pt semibold.
    Second line 8.5pt: "compared with the new regime, on a total income of ₹7,37,600".
  This is the one large colour block in the document. HARD: it says the regime name and
  the rupee saving and nothing else. No icons, no exclamation marks.

  THE TWO-COLUMN VERDICT: side-by-side panels, each 50% width, hairline bordered, the
  recommended one carrying a 2pt ACCENT left edge and the other plain.
    OLD REGIME                          NEW REGIME
    Total income      7,37,600          Total income      13,50,000
    Total tax           62,420          Total tax            85,800
    Taxes already paid 1,45,000         Taxes already paid 1,45,000
    ──────────────────────────          ──────────────────────────
    REFUND DUE          82,580          REFUND DUE           59,200
  The result line is 12pt semibold, POSITIVE when a refund, NEGATIVE when payable, with
  the label switching between "REFUND DUE" and "TAX PAYABLE". HARD: both regimes show
  their own refund-or-payable outcome. The taxpayer needs to see what lands in the bank
  account under each choice, not only the liability.

  WHY panel: the `reasons` bullets from the comparison agent, 9pt, tight leading,
  a hairline box, no bullet glyphs fancier than a small square.

  THE SWING CHART: one horizontal bar pair, 60pt tall total, showing the two liabilities
  on a common axis with the saving annotated between them. Draw it with ReportLab
  primitives or an embedded SVG. HARD: no pie chart, no 3D, no gradient fill, no legend
  when two labelled bars make the legend redundant. Axis labelled in lakhs.

  ACTION box at the foot: what the taxpayer does next, in three numbered lines - e.g.
  "1. File ITR-1 selecting the old regime in the return. 2. Form 10-IEA is not required
  as you have no business income. 3. Verify within 30 days by Aadhaar OTP."

PAGE 2 - LINE-BY-LINE COMPARISON (section 2)
  One table, the full `deltas` list, four columns: Particulars | Old regime | New regime |
  Difference. Group rows under sub-heads (Salary, House property, Capital gains, Other
  sources, Deductions, Tax computation, Taxes paid) with a 8.5pt semibold INK sub-head row
  on #F6F8FA. Difference column: POSITIVE when the old regime is cheaper on that line,
  NEGATIVE otherwise, always in parentheses when negative. Total row in 10pt semibold with
  a rule above. This table is the heart of the document; give it a full page and do not
  compress it.

PAGE 3 - WHAT THE NEW REGIME COSTS YOU (section 3)
  Table: every deduction and exemption claimed, its amount, whether the new regime allows
  it, and the tax value of it at the old-regime marginal rate. Foot the tax-value column.
  Then the BREAKEVEN paragraph in a hairline box: "The old regime is cheaper for you once
  your deductions and exemptions exceed ₹X. You currently claim ₹Y, which is ₹Z above that
  line." Then the SENSITIVITY table from the comparison agent's sensitivity(): deduction
  delta, old tax, new tax, which wins - so the taxpayer can see how fragile the
  recommendation is. Then, only when the old regime is recommended or within ₹25,000 of
  winning, the HEADROOM table (80C, 80CCD(1B), 80D unused). Suppress it otherwise.

PAGES 4-5 - COMPUTATION SHEETS (sections 4 and 5)
  One full computation sheet per regime, laid out exactly as a CA's computation of income:
  head by head, every statutory reference printed in a narrow MUTED column
  ("u/s 16(ia)", "u/s 24(b)", "u/s 80C"), amounts right-aligned, sub-totals ruled,
  Gross Total Income and Total Income in semibold. Then the tax computation block: tax at
  slab rates, tax at each special rate shown separately with its section, rebate u/s 87A,
  marginal relief, surcharge, health and education cess, total tax liability.
  HARD: the section reference column is what makes this read as a professional document
  rather than a calculator printout. Every single line gets one.

PAGE 6 - TAXES PAID, REFUND OR PAYABLE (section 6)
  TDS ledger by deductor: deductor name, TAN, section, amount per Form 16/26AS, amount
  claimed, matched flag. Advance tax and self-assessment challans with BSR code, challan
  serial number and date. Then the settlement block, under the recommended regime:
      Total tax liability              62,420
      Less: TDS on salary            1,45,000
      Less: Advance tax                     0
      Less: Self-assessment tax             0
      ────────────────────────────────────────
      REFUND DUE                       82,580
  with interest u/s 234A/234B/234C and fee u/s 234F shown as separate lines whenever
  non-zero, above the settlement line, and 244A refund interest noted below it as an
  estimate the department computes. Print the refund amount in words underneath.
  Then the bank account for the refund, masked to the last four digits, with the IFSC.
  Repeat the same settlement block for the NON-recommended regime in a smaller secondary
  panel, so the "vice versa" case is explicit: if the taxpayer would owe money under the
  other regime, the amount payable and the due date appear there.

PAGE 7 - DOCUMENT AND RECONCILIATION REGISTER (section 7)
  Every source document ingested: type, issuer, identifier (TAN/certificate number),
  pages, extraction path (offline parser / vision model / cloud), and overall confidence.
  Then the reconciliation table: Form 16 vs 26AS vs AIS for salary, TDS, interest and
  dividends, with the variance column and a matched/mismatched flag.

PAGE 8 - VERIFICATION AND SELF-HEALING AUDIT (section 8)
  The verification check list: check name, weight, result, message. Then the remediation
  ledger: attempt, agent, field, old value, new value, reason. Then the pipeline run
  summary: each agent, duration, tokens where relevant, status. Close with the full
  disclaimer paragraph and a signature block reading "Prepared by: Self-Healing Tax Filing
  System v<version>  ·  Reviewed by: ______________________ (Chartered Accountant)".

Implementation notes:
 - Build in two passes for accurate "Page X of Y" (NumberedCanvas pattern).
 - Every number that appears in the PDF must be read from RegimeTaxResult or
   RegimeComparison. The PDF layer performs NO arithmetic beyond formatting and summing a
   column it also prints. HARD: if the PDF computes a figure the engine did not, the two
   can diverge, and a divergence in a tax document is fatal.
 - Set PDF metadata: title, author, subject, and keywords including the PAN hash (not the
   PAN), plus /CreationDate in IST.
 - Emit an A4 print-safe file under 2 MB.

Write backend/tests/integration/test_comparison_report.py that builds the report for all
five golden vectors, asserts the PDF opens with PyMuPDF, has the expected page count,
contains the recommended regime string, contains the correctly Indian-grouped savings
figure, and that every page carries the footer disclaimer. Also assert the negative case:
a payable outcome renders "TAX PAYABLE" in the NEGATIVE colour and prints a due date.
```

**Done when:** the PDF for golden case 1 shows OLD REGIME, ₹23,380 saved, ₹82,580 refund under old and ₹59,200 under new, with Indian digit grouping everywhere and no default Helvetica on the page.

---

### Milestone 10 - ITR JSON export and the e-filing boundary

```
PROMPT FOR ANTIGRAVITY - MILESTONE 10

Create backend/app/itr/ with builders that emit the Income Tax Department's ITR JSON.

  itr/schema_loader.py   - loads the official JSON schema for the AY from
                           backend/assets/itr_schemas/ (vendored, versioned by AY) and
                           validates the built payload with jsonschema. Do not hand-write
                           the schema; download the published one for AY 2026-27 and check
                           it in, with a README noting the download date and source URL.
  itr/itr1_builder.py    - ITR-1 SAHAJ
  itr/itr2_builder.py    - ITR-2 (capital gains, multiple house properties)
  itr/itr4_builder.py    - ITR-4 SUGAM (presumptive)
  itr/form_selector.py   - implements the decision tree in section 1.13 and returns
                           (ITRForm, reasons: list[str]) so the verification agent and the
                           PDF can both explain the choice.

Each builder maps RegimeTaxResult + IndianTaxpayerData into the schema's nested blocks:
PersonalInfo, FilingStatus (including the regime flag and the Form 10-IEA acknowledgement
number when applicable), ScheduleS (salary), ScheduleHP, ScheduleCG, ScheduleOS,
ScheduleVIA, ScheduleTDS1/TDS2/TCS/IT, PartB-TI, PartB-TTI, Refund (bank details),
Verification. The regime election field is the one most likely to be wrong - unit-test both
values explicitly.

Rewrite backend/app/services/efile/backends.py:

  JsonSelfFileBackend  (default, channel="self_file")
      Returns accepted=True, status="ready_to_self_file", and instructions telling the
      taxpayer to log in at incometax.gov.in, go to e-File > Income Tax Returns > File
      Income Tax Return, choose "Import pre-filled data / Upload JSON", upload the file,
      and e-verify within 30 days by Aadhaar OTP, net banking, or by posting a signed
      ITR-V to CPC Bengaluru. No credentials are used by this system.

  MockEriBackend  (channel="eri_type2")
      Deterministic simulation of the ERI flow: Login -> Add Client (consent) -> Prefill ->
      Validate and Submit ITR -> e-Verify -> Acknowledgement. Only a verified, balanced
      return is "Accepted"; anything else returns a reject code. Generate a deterministic
      15-digit acknowledgement number from a hash of submission_id + date, formatted the
      way the ITD's acknowledgement number is. Document in the docstring that real ERI
      access requires registration with the Income Tax Department as a Type-2 e-Return
      Intermediary and that this class makes no network calls.

Add a get_backend(name) factory exactly like the existing one, and a settings-driven
choice. HARD: never add a backend that posts to incometax.gov.in. The repo must not
contain code that could be pointed at production with a credential.

Write tests: the ITR-1 payload validates against the vendored schema for golden case 1;
the ITR-2 payload validates for golden case 4 (capital gains); form_selector rejects ITR-1
when STCG is present and explains why; MockEriBackend rejects an unverified return.
```

**Done when:** a generated ITR JSON for each golden case validates against the vendored official schema.

---

### Milestone 11 - Frontend

```
PROMPT FOR ANTIGRAVITY - MILESTONE 11

Update the React/Vite frontend.

1. Regenerate frontend/src/types/tax.ts from the new Pydantic models. Prefer generating it
   (datamodel-code-generator or a small script over the OpenAPI schema FastAPI already
   serves) rather than hand-typing, so the contract cannot drift.

2. frontend/src/utils/inr.ts - the same Indian digit grouping as the PDF, plus a
   formatLakhs helper for chart axes. Unit-test it against the same 12 boundary values.

3. frontend/src/components/AgentPipeline.tsx - render 8 nodes with the parallel branch:
   the old-regime and new-regime nodes sit side by side between Income Computation and
   Comparison. Animate node state from the workflow status enum. Show the remediation loop
   as a returning edge with the attempt counter on it.

4. frontend/src/components/RegimeComparison.tsx - a new component:
   - the recommendation banner mirroring the PDF (same wording, same numbers)
   - a two-column liability card with the refund-or-payable outcome per regime
   - the line-by-line delta table, collapsible by sub-head
   - the sensitivity slider: drag total deductions from ₹0 to ₹4,00,000 and watch the two
     liabilities and the winner update. Call a POST /api/v1/submissions/{id}/sensitivity
     endpoint that re-runs the real engines; do NOT reimplement tax logic in TypeScript.
     HARD: there must be exactly one tax engine in this system and it must be the Python one.

5. Upload UI: accept multiple documents with a type selector (Form 16, 26AS, AIS, broker
   P&L, interest certificate, home loan certificate, rent receipts), show per-document
   extraction confidence, and let the user correct a low-confidence field inline, which
   re-triggers computation but records the manual override in the audit trail.

6. Download buttons: the comparison PDF, the ITR JSON, and the audit trail JSON.
```

**Done when:** the whole flow runs in the browser from multi-document upload to PDF download, and the sensitivity slider round-trips to the Python engine.

---

### Milestone 12 - Tests, evaluation and demo assets

```
PROMPT FOR ANTIGRAVITY - MILESTONE 12

1. Extend backend/app/synthetic/generator.py to emit a realistic corpus: Form 16 Part A+B
   PDFs for 8 taxpayer personas, matching 26AS extracts, AIS extracts, Zerodha-style P&L
   CSVs, bank interest certificates and home loan certificates. Personas: fresher on
   ₹6L, mid-career salaried ₹15L with home loan and HRA, senior citizen pensioner,
   equity trader with STCG and LTCG, freelancer under 44ADA, salaried with rental income,
   high earner at ₹60L crossing the surcharge threshold, and a job-changer with two
   Form 16s. Every persona is generated from a seed so the corpus is reproducible - record
   the seed in the fixture file name.

2. backend/tests/integration/test_end_to_end_india.py: run the full LangGraph for each
   persona and assert the recommended regime, total tax under both regimes, refund or
   payable, ITR form selected, and verification confidence. These are regression tests for
   the whole system, so pin the expected numbers.

3. backend/tests/eval/test_extraction_eval.py: extraction accuracy per field across the
   corpus, reported as exact-match rate and mean absolute rupee error, with a floor the
   test enforces (start at 0.95 exact match on Form 16 numeric fields). Report the model
   name, prompt version and seed alongside every number - a single-run accuracy figure
   with no config recorded is not a result.

4. A tax-law regression suite, backend/tests/unit/test_golden_vectors.py, parametrized over
   the table in section 5. Any change to a rule pack that moves one of these numbers must
   break the build loudly.

5. docs/architecture.md: rewrite for the Indian pipeline; embed the new architecture
   diagram. docs/tax-rules-coverage.md: a table of every implemented and explicitly
   unimplemented provision, so the scope boundary is documented rather than discovered.

6. A demo script (scripts/demo.py) that runs the mid-career persona end to end and opens
   the PDF, so the whole thing can be shown in 90 seconds.
```

**Done when:** `pytest backend/tests` is green, the eval floor holds, and `python scripts/demo.py` produces a PDF from a cold start.

---

## 4. PDF design specification

This exists separately from Milestone 9 because it is the part most likely to be done badly, and "make it look professional" is not an instruction a model can act on. These are the rules that separate a document that looks like it came from a chartered accountant's office from one that looks like a language model made a table.

### 4.1 The seven tells of a machine-made document, and the fix

| Tell | Fix |
|---|---|
| Default Helvetica or Times throughout | Vendor and register a real family: Source Sans 3 or Inter, Regular/Semibold/Bold. Numbers in tabular figures |
| Western digit grouping (₹1,234,567) | Indian grouping (₹12,34,567). Write the formatter first and unit-test it |
| Emoji, checkmark glyphs, coloured icons, rounded cards | None. A hairline rule and whitespace do the same work |
| Every section in a different colour | One accent, one positive, one negative, three neutrals. Six colours total |
| Heavy table borders and full grids | Hairlines under headers and above totals only. No vertical rules |
| Centred body text, inconsistent alignment | Labels left, numbers right, decimal-aligned, one decimal policy per column |
| No document identity | Page X of Y, document ID, generation timestamp in IST, masked PAN in the running header, preparer signature block |

### 4.2 Typography scale

| Element | Size | Weight | Colour |
|---|---|---|---|
| Product masthead | 16pt | Semibold | INK |
| Document title | 13pt | Regular | INK |
| Banner text | 14pt | Semibold | white on ACCENT |
| Section header | 10.5pt | Semibold | white on ACCENT bar |
| Sub-head row | 8.5pt | Semibold | INK on #F6F8FA |
| Table header | 8.5pt | Semibold | white on ACCENT |
| Body / table body | 9pt | Regular | INK |
| Section reference column | 7.5pt | Regular | MUTED |
| Caption, footer | 7pt | Regular | MUTED |
| Result figure (refund/payable) | 12pt | Semibold | POSITIVE or NEGATIVE |

Leading is 1.3x the size everywhere. Vertical rhythm: 6pt between rows inside a table, 9pt between tables, 14pt before a section header.

### 4.3 Grid

Content width = A4 width (210mm) minus 18mm margins each side = 174mm. Every table spans either the full 174mm or exactly half (85mm with a 4mm gutter). Nothing sits at an arbitrary width. Numeric columns are 26mm; the section-reference column is 16mm; particulars take the remainder.

### 4.4 Colour use rules

- ACCENT fills exactly two kinds of element: the recommendation banner and section header bars. Nothing else gets a filled background except the #F6F8FA sub-head rows.
- POSITIVE and NEGATIVE colour **numbers only**, never whole rows, never backgrounds.
- The recommended regime is distinguished by a 2pt accent left edge and semibold labels, not by a coloured panel. Restraint reads as confidence.

### 4.5 What the taxpayer must be able to answer after 30 seconds on page 1

1. Which regime should I pick?
2. How much do I save by picking it?
3. How much money do I get back, or have to pay, under each?
4. Why?
5. What do I do next?

If any of those five needs page 2, page 1 is wrong.

---

## 5. Golden test vectors (hand-verified)

All figures are FY 2025-26 / AY 2026-27, resident individual, computed with the rules in
section 1 and independently verified. **These are the acceptance criteria for Milestone 4.**
Every number below was produced by a reference implementation and checked by hand against
the slab tables.

### Case 1 - Mid-career salaried, heavy old-regime claims → OLD wins

Inputs: gross salary ₹15,00,000; HRA exemption ₹2,00,000; professional tax ₹2,400;
self-occupied home-loan interest ₹2,00,000; savings interest ₹15,000; 80C ₹1,50,000;
80D ₹25,000; 80CCD(1B) ₹50,000; employer NPS 80CCD(2) ₹90,000; 80TTA ₹10,000;
TDS ₹1,45,000. (The taxpayer rents in one city and owns the self-occupied house in
another, which is what makes HRA and 24(b) claimable together.)

| Line | Old regime | New regime |
|---|---|---|
| Gross salary | 15,00,000 | 15,00,000 |
| Less: HRA exempt u/s 10(13A) | (2,00,000) | - |
| Less: Standard deduction u/s 16(ia) | (50,000) | (75,000) |
| Less: Professional tax u/s 16(iii) | (2,400) | - |
| **Income from salary** | **12,47,600** | **14,25,000** |
| House property (self-occupied interest u/s 24(b)) | (2,00,000) | - |
| Income from other sources | 15,000 | 15,000 |
| **Gross total income** | **10,62,600** | **14,40,000** |
| Chapter VI-A (80C 1,50,000 + 80D 25,000 + 80CCD(1B) 50,000 + 80CCD(2) 90,000 + 80TTA 10,000) | (3,25,000) | (90,000) |
| **Total income** | **7,37,600** | **13,50,000** |
| Tax at slab rates | 60,020 | 82,500 |
| Rebate u/s 87A | 0 | 0 |
| Health & education cess @ 4% | 2,400 | 3,300 |
| **Total tax liability** | **62,420** | **85,800** |
| Less: TDS | 1,45,000 | 1,45,000 |
| **Refund due** | **82,580** | **59,200** |

**Recommendation: OLD REGIME. Saving ₹23,380.**

**Breakeven check (Milestone 5):** holding gross income at ₹15,15,000, the two regimes are
equal when total old-regime deductions and exemptions are ₹6,65,000 (old-regime total income
₹8,50,000, tax ₹82,500 + 4% cess = ₹85,800, matching the new regime exactly). This taxpayer
claims ₹7,77,400, which is ₹1,12,400 past the line. The bisection in Milestone 5 must land on
₹6,65,000 to the rupee.

### Case 2 - Salaried ₹12,00,000, thin claims → NEW wins by a mile

Inputs: gross salary ₹12,00,000; 80C ₹50,000 only; no HRA; no home loan.

| Line | Old regime | New regime |
|---|---|---|
| Gross salary | 12,00,000 | 12,00,000 |
| Less: Standard deduction | (50,000) | (75,000) |
| Less: 80C | (50,000) | - |
| **Total income** | **11,00,000** | **11,25,000** |
| Tax at slab rates | 1,42,500 | 52,500 |
| Rebate u/s 87A | 0 | (52,500) |
| Cess @ 4% | 5,700 | 0 |
| **Total tax liability** | **1,48,200** | **0** |

**Recommendation: NEW REGIME. Saving ₹1,48,200.** The ₹60,000 rebate absorbs the entire
liability because total income stays under ₹12,00,000. No amount of 80C investment can
make the old regime competitive here, and the report's reasons list must say exactly that.

### Case 3 - The 87A marginal relief band, new regime

| Total income | Tax after rebate and relief | Total with 4% cess |
|---|---|---|
| 12,00,000 | 0 | 0 |
| 12,10,000 | 10,000 | 10,400 |
| 12,50,000 | 50,000 | 52,000 |
| 12,70,588 | 70,588 (breakeven) | 73,412 |
| 12,75,000 | 71,250 (normal tax, relief exhausted) | 74,100 |
| 13,00,000 | 75,000 | 78,000 |

Relief equals `total_income - 12,00,000` until normal tax falls below that, which happens
at ₹12,70,588. A test must assert relief is exactly zero at and above ₹12,75,000.

### Case 4 - Surcharge plus capital gains, total income ₹60,00,000

Of which ₹10,00,000 is taxable LTCG u/s 112A (after the ₹1,25,000 exemption) and
₹50,00,000 is normal income.

| Line | Old regime | New regime |
|---|---|---|
| Tax at slab rates on ₹50,00,000 | 13,12,500 | 10,80,000 |
| Tax on LTCG u/s 112A @ 12.5% | 1,25,000 | 1,25,000 |
| Surcharge @ 10% | 1,43,750 | 1,20,500 |
| Cess @ 4% | 63,250 | 53,020 |
| **Total tax liability** | **16,44,500** | **13,78,520** |

At ₹60,00,000 the surcharge rate is 10%, below the 15% special-income cap, so no split is
needed. Add a second fixture at total income ₹2,50,00,000 with LTCG to exercise the cap.

### Case 5 - Senior citizen pensioner, pension ₹9,00,000

Claims 80D ₹50,000 (senior) and 80TTB ₹50,000 under the old regime.

| Line | Old regime (senior slabs) | New regime |
|---|---|---|
| Less: Standard deduction | (50,000) | (75,000) |
| Less: 80D + 80TTB | (1,00,000) | - |
| **Total income** | **7,50,000** | **8,25,000** |
| Tax at slab rates | 60,000 | 22,500 |
| Rebate u/s 87A | 0 | (22,500) |
| Cess | 2,400 | 0 |
| **Total tax liability** | **62,400** | **0** |

**Recommendation: NEW REGIME.** The senior citizen's higher basic exemption in the old
regime is worth ₹2,500; the new regime's rebate is worth ₹22,500. This case exists
specifically to stop the common assumption that seniors always do better under the old
regime.

### Case 6 - Surcharge marginal relief at the ₹50,00,000 threshold, new regime

| Total income | Surcharge | Total tax |
|---|---|---|
| 50,00,000 | 0 | 11,23,200 |
| 50,50,000 | 35,000 (relieved from 1,09,500) | 11,75,200 |
| 51,00,000 | 70,000 (relieved from 1,14,000) | 12,27,200 |
| 52,00,000 | 1,14,000 (no relief needed) | 13,04,160 |

Relief applies until the surcharge stops exceeding the incremental income, which happens
between ₹51,00,000 and ₹52,00,000. A test must assert relief is zero at ₹52,00,000.

---
## 6. Scope boundary, risks and compliance

### 6.1 In scope

Resident individuals with salary, one or two house properties, capital gains, presumptive
business or professional income under 44AD/44ADA/44AE, and income from other sources.
ITR-1, ITR-2 and ITR-4. Both regimes. Self-filing package output.

### 6.2 Explicitly out of scope - say so in the README rather than half-building it

Books-of-account business income with balance sheet and P&L (full ITR-3), audit cases
u/s 44AB, HUFs, firms, companies, trusts, non-residents claiming DTAA relief u/s 90/91
(the relief field exists but is taxpayer-entered, not computed), foreign assets and
Schedule FA, ESOP tax deferral for eligible start-ups, clubbing of income u/s 60-64,
Section 89 relief computation for arrears, agricultural income aggregation for rate
purposes above ₹5,000, and trust/charity provisions. Each of these is a semester of work
on its own, and a half-implemented one is worse than an absent one because it fails
silently.

### 6.3 The single biggest technical risk, and the mitigation

**Extraction, not computation.** The maths is closed-form and testable; the Form 16 you get
from a small employer's payroll vendor is a scanned image with a stamp across the numbers.
Everything in this system is downstream of getting the right rupee off the page.

Mitigations, in order of value:
1. Cross-footing. A Form 16 is internally redundant - 17(1)+17(2)+17(3) must equal gross
   salary, and gross minus exemptions minus section 16 must equal the salary head. Use the
   redundancy as a free correctness oracle on every extraction.
2. Three-way reconciliation against 26AS and AIS, which are machine-generated and clean.
   Any figure that also appears in AIS should be taken from AIS.
3. Confidence-gated human correction in the UI, with the override recorded in the audit
   trail. A system that admits "I am 62% sure this is ₹14,50,000, please confirm" is
   trustworthy; one that guesses silently is not.
4. Escalation to manual review after two failed remediation passes, never an unbounded loop.

### 6.4 The legal risk

Do not represent this as a filing service. Do not accept anyone's real PAN credentials. Do
not store real Form 16s beyond a session without an explicit retention policy, and note
that Indian tax documents attract the DPDP Act 2023 obligations for personal data. Keep the
default e-file backend at `json_self_file`, keep `DISCLAIMER.md` in the repo root, and put
the disclaimer in the PDF footer on every page.

### 6.5 The Income-tax Act 2025 transition

From 1 April 2026 the Income-tax Act 2025 replaces the 1961 Act. Rates, slabs, the standard
deduction and the regime structure carry over unchanged; the sections are renumbered
(115BAC → 202, 80C → 123, 192 → 392, 139 → 263) and "tax year" replaces the previous
year / assessment year pair. Income earned before 1 April 2026 stays under the 1961 Act
even though it is assessed later.

The practical consequence for this project: **section labels are data, not string
literals**. Put the section map in the year's parameter pack (`section_map` in
`fy_2026_27.py`) and have the PDF and the UI read labels from it. If you hard-code "u/s
80C" in a template, the FY 2026-27 report will be wrong and you will be chasing strings
through a dozen files. This is a ten-minute decision at Milestone 2 that saves a day later.

### 6.6 Build order and why

M0 → M1 → M2 → M3 → M4 → M5 are the critical path and must be done in order; each one is
the contract the next depends on. M6 (reading) is the longest and can start in parallel
with M4/M5 once the schemas from M1 are frozen, because it only has to produce
`IndianTaxpayerData`. M7, M8 depend on M4/M5. M9 (PDF) depends on M5 and is the highest-
value single milestone for a demo, so if time is short, build M0-M5 plus M9 with
hand-entered data and treat M6 as the stretch. A system that computes and explains the
regime choice perfectly from typed input is a better project than one that reads PDFs
badly and computes nothing.

---

## 7. Recommendation

**Do the conversion, and make the Regime Comparison Agent the product rather than a
feature.** The US version's headline claim - self-healing multi-agent verification - is
architecture, and architecture does not demo. The Indian version has a claim that a
non-technical person feels immediately: *two legal ways to compute your tax, here is the
rupee difference, here is which one to pick and what it costs you either way.* That is the
thing to put on the first page of the PDF and the first slide of the review.

**Confidence: high on the architecture and the tax engine, medium on extraction.** The
five-head computation, dual-regime comparison and the verification gate are all
deterministic, fully testable, and specified to the rupee in section 5. The risk sits
entirely in Milestone 6. Budget your time accordingly: the maths will work on the first
try, the Form 16 parser will not.

**What would prove this approach wrong:**

1. **If the golden vectors in section 5 do not reproduce.** They are the falsifiable core.
   If a correctly implemented engine disagrees with the hand-computed table, the rules in
   section 1 are wrong and the whole rulebook needs re-verification against the bare Act
   before another line is written.
2. **If extraction accuracy on real Form 16s stays below about 90% exact match on numeric
   fields after the cross-foot and reconciliation passes.** Below that, the self-healing
   loop spends every run remediating and the system is slower and less accurate than typing
   eight numbers into a form. If you hit that wall, pivot the input to AIS/26AS JSON
   downloads plus a short manual salary form and keep the extraction as an optional path.
3. **If a chartered accountant reviewing the output finds a systematic error in the
   comparison** - not a rounding difference, but a missed interaction such as the 87A
   marginal relief, the 15% surcharge cap on special income, or the ₹2,00,000 house-property
   set-off limit. Those three interactions are where free online calculators are commonly
   wrong, which is exactly why getting them right is the defensible contribution. Get one
   CA to review the PDF for case 1 and case 4 before the final review; that single review
   is worth more than another week of features.
4. **If the recommendation flips under small input perturbations without the report saying
   so.** The sensitivity table in Milestone 5 exists to catch this. A recommendation that
   swings on ₹5,000 of deduction is a recommendation that has to be presented as close,
   not as a verdict.

**Verify before you rely on any number in section 1:** the slab tables, 87A limits,
surcharge bands and capital-gains rates here were checked against the Income Tax
Department's own pages and standard references in September 2026, but the position on
whether the 87A rebate reaches Section 111A short-term gains under the new regime has moved
in recent Finance Acts and is the one item worth confirming against the bare Act text
before you ship. Everything marked `verified=False` in Milestone 2 is there for the same
reason.

---

## Appendix A - Quick start checklist

```
[ ] Fork the repo, create branch `india-conversion`
[ ] M0  strip US modules, scaffold, DISCLAIMER.md
[ ] M1  schemas + PAN/IFSC validators + tests
[ ] M2  fy_2025_26.py + fy_2026_27.py + validation + tests
[ ] M3  five-head income computation + tests
[ ] M4  dual regime engines + golden vectors GREEN      <- hard gate
[ ] M5  regime comparison agent + graph fan-out
[ ] M9  comparison PDF  (pull this forward if time is short)
[ ] M6  Indian document extraction
[ ] M7  verification check pack
[ ] M8  remediation mapping
[ ] M10 ITR JSON + e-file adapters
[ ] M11 frontend
[ ] M12 corpus, eval, docs, demo script
[ ] CA review of the PDF for golden cases 1 and 4
```

## Appendix B - Sources

- [Income Tax Department: Salaried individuals, AY 2026-27](https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1)
- [Income Tax Department: Form 10-IEA FAQ](https://www.incometax.gov.in/iec/foportal/help/statutory-forms/popular-form/form-10-IEA-faq)
- [Income Tax Department: API specifications (ERI Type-2)](https://www.incometax.gov.in/iec/foportal/api-specifications)
- [ClearTax: Income tax slabs FY 2025-26 and FY 2026-27](https://cleartax.in/s/income-tax-slabs)
- [Axis Max Life: Income tax slabs FY 2026-27 (Budget 2026 left slabs unchanged)](https://www.axismaxlife.com/blog/tax-savings/income-tax-slab-2026-27)
- [Tax2win: Section 87A rebate and marginal relief](https://tax2win.in/guide/section-87a)
- [Tax2win: Surcharge rates and marginal relief](https://tax2win.in/guide/income-tax-surcharge-and-marginal-relief)
- [Tax2win: ITR filing due dates AY 2026-27](https://tax2win.in/guide/ay-2026-27-itr-filing-last-date-august-31)
- [Finnovate: Capital gains tax rates FY 2025-26](https://www.finnovate.in/learn/blog/capital-gains-tax-india-explained)
- [CalcGuru: Deductions allowed under the new and old regimes](https://calcguru.in/income-tax-deductions/)
- [CalcGuru: 234A / 234B / 234C interest and 234F fee](https://calcguru.in/234a-234b-234c-interest-calculator/)
- [Taxonation: Income-tax Act 2025 vs 1961 section mapping](https://taxonation.com/show-detail-article/279744/income-tax-act-2025-vs-1961-the-complete-section-mapping-guide)
