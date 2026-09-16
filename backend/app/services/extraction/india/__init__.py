"""Indian Document Extraction Parsers."""

from app.services.extraction.india.ais_parser import AISParser
from app.services.extraction.india.broker_pnl_parser import BrokerPnLParser
from app.services.extraction.india.certificate_parsers import (
    HomeLoanCertificateParser,
    InterestCertificateParser,
    RentReceiptParser,
)
from app.services.extraction.india.form16_parser import Form16Parser
from app.services.extraction.india.form26as_parser import Form26ASParser

__all__ = [
    "AISParser",
    "BrokerPnLParser",
    "Form16Parser",
    "Form26ASParser",
    "HomeLoanCertificateParser",
    "InterestCertificateParser",
    "RentReceiptParser",
]
