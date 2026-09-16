"""PDF services for Regime Comparison Report."""

from app.services.pdf.comparison_report import (
    ComparisonReportService,
    ProfessionalReportService,
)
from app.services.pdf.style import inr, inr_words

__all__ = [
    "ComparisonReportService",
    "ProfessionalReportService",
    "inr",
    "inr_words",
]
