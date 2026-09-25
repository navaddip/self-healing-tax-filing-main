import json
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings

BACKEND = Path(__file__).resolve().parents[2]


def test_migrations_number_submissions_and_expose_taxpayer_details(tmp_path, monkeypatch):
    db = tmp_path / "tax.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db.as_posix()}")
    get_settings.cache_clear()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    try:
        command.upgrade(cfg, "0002")
        state = {
            "status": "completed",
            "extracted_data": {"name": "Asha Rao", "pan": "ABC****4F", "date_of_birth": "1990-05-01",
                               "form16s": [{"employer_name": "Acme"}], "taxes_paid": {"tds_salary": "50000"}},
            "comparison": {"recommended": "old", "savings": "1000",
                           "old": {"total_tax_liability": "40000", "refund_due": "10000", "tax_payable": "0",
                                   "interest_234b": "120", "fee_234f": "0", "income": {"total_income": "900000"}},
                           "new": {"total_tax_liability": "41000", "refund_due": "9000", "tax_payable": "0",
                                   "income": {"gross_salary": "975000", "total_income": "900000"}}},
        }
        with sqlite3.connect(db) as conn:
            for i, created in enumerate(["2026-01-02", "2026-01-01"]):
                conn.execute(
                    "INSERT INTO submissions (id, original_filename, upload_path, status, result_json, created_at, updated_at) "
                    "VALUES (?, 'f.pdf', 'x', 'completed', ?, ?, ?)",
                    (f"id-{i}", json.dumps(state), created, created),
                )
        command.upgrade(cfg, "head")
        with sqlite3.connect(db) as conn:
            conn.row_factory = sqlite3.Row
            assert [r["id"] for r in conn.execute("SELECT id FROM submissions ORDER BY serial_no")] == ["id-1", "id-0"]
            row = conn.execute("SELECT * FROM taxpayer_details WHERE name LIKE '%asha%' AND serial_no = 1").fetchone()
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(submissions)")}
        assert "filing_details_json" in columns
        assert row["date_of_birth"] == "1990-05-01"
        assert row["employer_name"] == "Acme"
        assert row["gross_salary"] == "975000"
        assert row["tax_old_regime"] == "40000"
        assert row["refund_due"] == "10000"  # recommended (old) regime
        assert float(row["interest_and_fees"]) == 120
    finally:
        get_settings.cache_clear()
