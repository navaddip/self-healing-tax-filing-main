"""Broker Tax P&L Statement Parser.

Parses equity trade statements (Zerodha Console, Groww, Upstox, generic CSV)
into typed CapitalGainItem records. Recomputes holding periods from buy/sell dates
rather than blindly trusting broker classifications.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.schemas.tax import CapitalGainItem, SourceEvidence


def _clean_amount(text: str) -> Decimal:
    cleaned = re.sub(r"[^\d.\-]", "", text)
    if not cleaned or cleaned == "-":
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def _parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


class BrokerPnLParser:
    """Parses Zerodha/Groww/Generic broker P&L CSV and normalises to CapitalGainItem."""

    def parse_csv(
        self, csv_text: str
    ) -> tuple[list[CapitalGainItem], list[SourceEvidence], list[str]]:
        items: list[CapitalGainItem] = []
        evidence: list[SourceEvidence] = []
        warnings: list[str] = []

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            return items, evidence, warnings

        # Normalise header names
        norm_map = {}
        for fn in reader.fieldnames:
            clean = fn.strip().lower().replace(" ", "_")
            norm_map[clean] = fn

        cutoff_date = date(2024, 7, 23)

        for row_idx, raw_row in enumerate(reader, start=1):
            row = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in raw_row.items() if k}

            symbol = row.get("symbol") or row.get("stock_symbol") or row.get("scrip_name") or f"Item_{row_idx}"
            buy_dt_str = row.get("buy_date") or row.get("purchase_date") or ""
            sell_dt_str = row.get("sell_date") or row.get("exit_date") or ""

            buy_date = _parse_date(buy_dt_str)
            sell_date = _parse_date(sell_dt_str)

            buy_val = _clean_amount(row.get("buy_value") or row.get("buy_total") or "0")
            sell_val = _clean_amount(row.get("sell_value") or row.get("sell_total") or "0")
            expenses = _clean_amount(row.get("transfer_expenses") or row.get("charges") or "0")

            # Holding period determination
            days = 0
            if buy_date and sell_date:
                days = (sell_date - buy_date).days
                is_long = days > 365
            else:
                term_str = row.get("term") or row.get("type") or ""
                is_long = "long" in term_str.lower() or "ltcg" in term_str.lower()

            declared_term = row.get("term") or row.get("type") or ""
            if declared_term:
                declared_is_long = "long" in declared_term.lower() or "ltcg" in declared_term.lower()
                if is_long != declared_is_long:
                    warnings.append(
                        f"Row {row_idx} ({symbol}): broker classified as {declared_term} "
                        f"but dates indicate {'Long-term' if is_long else 'Short-term'} ({days} days)."
                    )

            is_pre_cutoff = buy_date is not None and buy_date < cutoff_date

            item = CapitalGainItem(
                asset_type="listed_equity",
                acquisition_date=buy_date,
                transfer_date=sell_date,
                cost_of_acquisition=buy_val,
                sale_consideration=sell_val,
                transfer_expenses=expenses,
                stt_paid=True,
                is_pre_23jul2024=is_pre_cutoff,
                holding_days=days,
                is_long_term=is_long,
            )
            items.append(item)

            evidence.append(
                SourceEvidence(
                    field_name=f"capital_gain_{symbol}_{row_idx}",
                    source_document="BrokerPnL",
                    page_number=1,
                    confidence=0.98,
                    raw_text=f"{symbol}: Buy ₹{buy_val} on {buy_dt_str}, Sell ₹{sell_val} on {sell_dt_str}",
                )
            )

        return items, evidence, warnings
