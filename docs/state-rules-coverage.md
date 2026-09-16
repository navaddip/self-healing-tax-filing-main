# State rule-pack coverage

Tracks the per-state income-tax rule packs under
`backend/app/state_rules/states/`. See `backend/app/state_rules/` for the
mechanism and the per-state recipe in this repo's planning notes.

Two tiers:

- **High-accuracy (`verified=True`)** — delegated to the `tenforty`
  (OpenTaxSolver) engine, which models the state's own base, deductions,
  exemptions and credits. Pinned by golden-case tests
  (`tests/unit/test_state_rules_tenforty.py`). Currently **CA, NY, NJ, AZ**.
  Each falls back to its reference pack if the engine errors.
  - *Social Security* is fully excluded for all four (correct-by-construction:
    the federally-taxable SS amount is injected only for states flagged as
    taxing it — none of these are).
  - *Age inputs*: optional `birth_date`/`spouse_birth_date` give exact age at
    the tax year-end (so NY's 59½ and NJ's "62 by year-end" boundaries are
    precise); otherwise the integer `age`/`spouse_age`, then the 65+ booleans.
  - *Pension/IRA* income is handled per state. CA taxes it in full. **NY**
    applies the $20,000 pension/annuity exclusion (N.Y. Tax Law 612(c)(3-a)) at
    59½. **NJ** is special: OTS *ignores long-term capital gains* and *fully
    excludes Schedule-1 income*, so NJ-taxable income is routed into the fields
    OTS-NJ does tax, and NJ's retirement exclusion (N.J.S.A. 54A:6-10, age 62+,
    phased out across $100k/$125k/$150k) **and** the Other Retirement Income
    Exclusion (54A:6-15, earned income ≤ $3,000) are computed in the adapter.
  - *Validation*: cross-checked against NBER TAXSIM. Note TAXSIM's federal stops
    at 2023 and its 2021+ state law is an NBER inflation-estimate, so it is *not*
    a 2025 oracle; where comparable (2023) our routing lands within a few percent
    and the NJ capital-gains/exclusion fixes track TAXSIM directionally. No
    engine is a perfect oracle — residual inter-engine differences are a few %.

### Layer-1 parameter verification (2026-07)

The 2025 parameters tenforty/OTS uses were backed out and diffed against
official sources. All four match:

| State | Official 2025 source | Reconciled |
|-------|----------------------|-----------|
| CA | FTB 2025 rate schedules + std deduction | std $5,706/$11,412 · $153 exemption credit · all 9 bracket edges (11,079 / 26,264 / … / 371,479) · rates 1–12.3% |
| NY | tax.ny.gov 2025 std deductions / IT-201-I | single std $8,000 · models the >$107,650 tax-benefit recapture |
| NJ | NJ-1040 instructions | $1,000 personal exemption · taxes capital gains (routed around the OTS-NJ LTCG bug) |
| AZ | A.R.S. 43-1011 / AZ DOR | 2.5% flat · std = federal $15,750 (conformed) |

Layer-2 (full-return match vs commercial tax software) remains for NY/NJ/AZ;
CA is validated by tenforty against professional software.
- **Reference (`verified=False`)** — hand-encoded brackets, transcribed from
  cited statutes/DOR tables but not reconciled against published returns. Good
  for ballpark; not for filing.

Legend: ✅ done · ⭐ high-accuracy (tenforty) · — no income tax (no pack needed)

## No income tax (no pack)

AK, FL, NV, SD, TN, TX, WY. WA taxes only capital gains (not wages) — treated as
no-pack unless a custom capital-gains pack is added later.

## Implemented (43 — all taxing jurisdictions)

| State | Type | Base | Notes |
|-------|------|------|-------|
| AL | progressive (2/4/5%) | fed AGI | std deduction / exemptions not modeled |
| AR | flat 3.9% (approx) | fed AGI | irregular schedule simplified to flat; overstates low income |
| AZ | ⭐ tenforty | engine | high-accuracy; reference flat 2.5% as fallback |
| CA | ⭐ tenforty | engine | high-accuracy (validated vs pro software); reference fallback |
| CO | flat 4.40% | fed taxable income | |
| CT | progressive | fed AGI | exemption phase-out / recapture not modeled |
| DC | progressive (top 10.75%) | fed taxable income | exemption / credits not modeled |
| DE | progressive (0–6.6%) | fed AGI | state std deduction; credits not modeled |
| GA | flat 5.19% (HB 111) | fed AGI | state std deduction |
| HI | progressive (top 11%) | fed AGI | std deduction; HOH approximated with single |
| IA | flat 3.8% | fed AGI | adjustments/exemptions not modeled |
| ID | flat 5.3% (HB 40) | fed taxable income | |
| IL | flat 4.95% | fed AGI | personal exemption not modeled |
| IN | flat 3.00% | fed AGI | local taxes / exemptions not modeled |
| KS | progressive (5.2/5.58%) | fed AGI | state std deduction |
| KY | flat 4.00% | fed AGI | state std deduction |
| LA | flat 3.0% | fed AGI | exemption/std deduction not modeled |
| MA | 5.0% + 4% surtax >$1,083,150 | fed AGI | 2-band; own deductions not modeled |
| MD | progressive | fed AGI | state only — county tax out of scope |
| ME | progressive | fed taxable income | exemption / credits not modeled |
| MI | flat 4.25% | fed AGI | personal exemption not modeled |
| MN | progressive | fed taxable income | 2024-indexed; subtractions/credits not modeled |
| MO | progressive (top 4.7%) | fed taxable income | modifications/credits not modeled |
| MS | 0% to $10k, then 4.4% | fed AGI | |
| MT | progressive (4.7/5.9%) | fed taxable income | adjustments/credits not modeled |
| NC | flat 4.25% | fed AGI | state std deduction |
| ND | progressive (0/1.95/2.5%) | fed taxable income | adjustments not modeled |
| NE | progressive (top 5.2%) | fed AGI | state std deduction; exemption credit not modeled |
| NH | interest/dividends (repealed 2025) | n/a | custom pack |
| NJ | ⭐ tenforty | engine | high-accuracy; reference progressive as fallback |
| NM | progressive | fed taxable income | pre-HB 252 schedule; 2025 restructure pending |
| NY | ⭐ tenforty | engine | high-accuracy; reference progressive as fallback |
| OH | 0% / 2.75% / 3.5% | fed AGI | exemptions / BID not modeled |
| OK | progressive (top 4.75%) | fed AGI | state std deduction; exemptions not modeled |
| OR | progressive | fed AGI | federal-tax subtraction not modeled (overstates) |
| PA | flat 3.07% | fed AGI | 8 income classes approximated |
| RI | progressive | fed AGI | state std deduction; phase-out not modeled |
| SC | progressive (top 6.2%) | fed taxable income | top rate trigger-dependent (6.2% vs 6.3%) |
| UT | flat 4.55% | fed AGI | taxpayer credit not modeled |
| VA | progressive | fed AGI | state std deduction; exemptions not modeled |
| VT | progressive | fed taxable income | exemptions / credits not modeled |
| WI | progressive | fed AGI | phased-out std deduction not modeled |
| WV | progressive (top 5.12%) | fed AGI | personal exemptions not modeled |

## Remaining

None — every taxing state plus DC has a pack; the eight no-income-tax states
need none. All packs are `verified=False` and await maintainer reconciliation
against the published 2025 returns.

### Highest-priority reconciliation flags

- **AR** — modeled as flat 3.9%; the real graduated low-income tables and bracket
  adjustment are not represented (overstates low-income filers).
- **GA / ID / SC** — 2025 rates depend on recently enacted cuts / revenue
  triggers (GA 5.19%, ID 5.3%, SC 6.2%); confirm against the state DOR.
- **NM** — HB 252 (2024) restructured brackets for 2025; pack still encodes the
  2024 schedule.
- **OR / WI** — income-limited federal-tax subtraction (OR) and phased-out
  standard deduction (WI) are not modeled, overstating tax.
- States marked "2024-indexed" need their 2025 inflation-adjusted bracket edges.

## Per-state recipe

1. Determine tax type, 2025 rate(s), starting base, and standard
   deduction/exemption from the statute + state DOR / Tax Foundation 2025
   summary.
2. Add `states/<state>_2025.py` (`FlatStatePack` / `BracketStatePack` / custom),
   `verified=False`, cited `source`, docstring listing what is not modeled.
3. Register in `states/__init__.py`.
4. Add a focused unit test asserting a reference-scenario amount.
5. Run `validate_all()` + pytest + ruff; update this checklist.
