"""Corporate income tax: 30% of chargeable income (revenue minus allowable deductions)."""

from decimal import Decimal

from a2.tax.base import Tax
from a2.tax.context import TaxContext, TaxResult
from a2.tax.money import Money

__all__ = ["CorporateIncomeTax"]


class CorporateIncomeTax(Tax):
    """Tax on a resident company's chargeable income. A loss gives zero tax and is reported."""

    name = "Corporate income tax"

    def __init__(self, rate: Decimal = Decimal("0.30")) -> None:
        if not isinstance(rate, Decimal) or not Decimal(0) <= rate <= Decimal(1):
            raise ValueError("rate must be a Decimal between 0 and 1")
        self.rate = rate

    def __repr__(self) -> str:
        return f"CorporateIncomeTax(rate={self.rate})"

    def calculate(self, ctx: TaxContext) -> TaxResult:
        revenue = ctx.require("revenue")
        chargeable = revenue - ctx.allowable_deductions
        if chargeable.is_negative() or chargeable == Money.zero():
            loss = -chargeable
            return TaxResult(self.name, Money.zero(), Money.zero(),
                             (("revenue", revenue), ("allowable deductions", ctx.allowable_deductions),
                              ("tax loss (carry-forward not modelled)", loss)))
        tax = chargeable * self.rate
        return TaxResult(self.name, chargeable, tax,
                         (("revenue", revenue), ("allowable deductions", ctx.allowable_deductions),
                          ("chargeable income", chargeable), (f"tax at {self.rate:.0%}", tax)))
