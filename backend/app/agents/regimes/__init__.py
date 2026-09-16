"""Dual regime tax calculation engines (Old Regime and New Regime u/s 115BAC)."""

from app.agents.regimes.new_regime import NewRegimeCalculator
from app.agents.regimes.old_regime import OldRegimeCalculator

__all__ = ["OldRegimeCalculator", "NewRegimeCalculator"]
