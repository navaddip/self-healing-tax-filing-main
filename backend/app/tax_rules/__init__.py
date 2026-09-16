"""Tax rule sets for India income tax.

Importing this package registers every installed tax year with the parameter
registry in :mod:`app.tax_rules.params` so ``get_params(year)`` can resolve them.
"""

from app.tax_rules import fy_2025_26, fy_2026_27  # noqa: F401  (side-effect: register)
from app.tax_rules.params import TaxYearParams, get_params

__all__ = ["TaxYearParams", "get_params", "fy_2025_26", "fy_2026_27"]
