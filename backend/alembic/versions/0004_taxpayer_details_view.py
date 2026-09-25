"""Readable, searchable view of each submission's taxpayer and tax details."""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

REC = "{rec}"  # placeholder for the recommended regime's JSON prefix

COLUMNS = [
    ("name", "extracted_data.name"),
    ("pan_masked", "extracted_data.pan"),
    ("date_of_birth", "extracted_data.date_of_birth"),
    ("age_band", "extracted_data.age_band"),
    ("residential_status", "extracted_data.residential_status"),
    ("financial_year", "extracted_data.financial_year"),
    ("assessment_year", "extracted_data.assessment_year"),
    ("employer_name", "extracted_data.form16s.0.employer_name"),
    ("employer_tan", "extracted_data.form16s.0.employer_tan"),
    ("gross_salary", "comparison.new.income.gross_salary"),
    ("exempt_allowances", "comparison.old.income.exempt_allowances"),
    ("house_property_income_old", "comparison.old.income.house_property_income"),
    ("capital_gains", "comparison.new.income.capital_gains_total"),
    ("other_sources_income", "comparison.new.income.other_sources_income"),
    ("gross_total_income_old", "comparison.old.income.gross_total_income"),
    ("gross_total_income_new", "comparison.new.income.gross_total_income"),
    ("chapter_via_deductions_old", "comparison.old.income.chapter_via_total"),
    ("taxable_income_old", "comparison.old.income.total_income"),
    ("taxable_income_new", "comparison.new.income.total_income"),
    ("tax_old_regime", "comparison.old.total_tax_liability"),
    ("tax_new_regime", "comparison.new.total_tax_liability"),
    ("recommended_regime", "comparison.recommended"),
    ("savings", "comparison.savings"),
    ("tds_salary", "extracted_data.taxes_paid.tds_salary"),
    ("taxes_paid_and_relief", f"comparison.{REC}.taxes_paid_total"),
    ("interest_and_fees", None),
    ("refund_due", f"comparison.{REC}.refund_due"),
    ("tax_payable", f"comparison.{REC}.tax_payable"),
    ("itr_form", "receipt.itr_form"),
    ("verification_confidence", "verification.confidence_score"),
]


def upgrade():
    postgres = op.get_bind().dialect.name == "postgresql"

    def get(path: str) -> str:
        if postgres:
            return "(result_json::json #>> '{%s}')" % path.replace(".", ",")
        parts = "".join(f"[{p}]" if p.isdigit() else f".{p}" for p in path.split("."))
        return f"json_extract(result_json, '${parts}')"

    def column(path: str) -> str:
        if REC not in path:
            return get(path)
        return (f"CASE WHEN {get('comparison.recommended')} = 'old' "
                f"THEN {get(path.replace(REC, 'old'))} ELSE {get(path.replace(REC, 'new'))} END")

    def interest() -> str:
        parts = [f"COALESCE(CAST({column(f'comparison.{REC}.{k}') } AS NUMERIC), 0)"
                 for k in ("interest_234a", "interest_234b", "interest_234c", "fee_234f")]
        return " + ".join(parts)

    selects = [f"{interest() if path is None else column(path)} AS {name}" for name, path in COLUMNS]
    op.execute(f"""
        CREATE VIEW taxpayer_details AS
        SELECT serial_no, id AS submission_id, status, created_at AS uploaded_at, original_filename,
               {', '.join(selects)},
               error, report_path
        FROM submissions
    """)


def downgrade():
    op.execute("DROP VIEW taxpayer_details")
