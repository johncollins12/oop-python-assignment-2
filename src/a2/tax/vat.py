"""Value Added Tax over a list of invoices: standard-rated, zero-rated and exempt supplies.

URA: standard-rated supplies are charged 18%, zero-rated 0%; exempt supplies attract no VAT.
Net VAT payable = output VAT (on sales) - input VAT (on purchases); a negative result is a credit.
"""

from dataclasses import dataclass
from decimal import Decimal

from a2.tax.base import Tax
from a2.tax.context import TaxContext, TaxResult
from a2.tax.errors import InvalidIncomeError
from a2.tax.money import Money

__all__ = ["Invoice", "VAT", "STANDARD", "ZERO_RATED", "EXEMPT", "SALE", "PURCHASE"]

STANDARD, ZERO_RATED, EXEMPT = "standard", "zero-rated", "exempt"
SALE, PURCHASE = "sale", "purchase"


@dataclass(frozen=True)
class Invoice:
    """One invoice. `amount` is VAT-exclusive unless `vat_inclusive` is True."""

    number: str
    kind: str
    supply: str
    amount: Money
    vat_inclusive: bool = False

    def __post_init__(self) -> None:
        if self.kind not in (SALE, PURCHASE):
            raise InvalidIncomeError(f"invoice {self.number}: kind must be {SALE!r} or {PURCHASE!r}")
        if self.supply not in (STANDARD, ZERO_RATED, EXEMPT):
            raise InvalidIncomeError(f"invoice {self.number}: unknown supply type {self.supply!r}")
        if not isinstance(self.amount, Money) or self.amount.is_negative():
            raise InvalidIncomeError(f"invoice {self.number}: amount must be a non-negative Money value")


class VAT(Tax):
    """Output VAT, input VAT and net VAT payable for the invoices in a TaxContext."""

    name = "VAT"

    def __init__(self, standard_rate: Decimal = Decimal("0.18")) -> None:
        if not isinstance(standard_rate, Decimal) or not Decimal(0) < standard_rate < Decimal(1):
            raise ValueError("standard_rate must be a Decimal between 0 and 1")
        self.rates = {STANDARD: standard_rate, ZERO_RATED: Decimal(0), EXEMPT: None}

    def __repr__(self) -> str:
        return f"VAT(standard_rate={self.rates[STANDARD]})"

    def split(self, invoice: Invoice) -> tuple[Money, Money]:
        """(net value, VAT) of one invoice. Exempt supplies carry no VAT at all."""
        rate = self.rates[invoice.supply]
        if rate is None or rate == 0:
            return invoice.amount, Money.zero()
        if invoice.vat_inclusive:
            vat = invoice.amount * (rate / (Decimal(1) + rate))
            return invoice.amount - vat, vat
        return invoice.amount, invoice.amount * rate

    def calculate(self, ctx: TaxContext) -> TaxResult:
        if not ctx.invoices:
            raise InvalidIncomeError("VAT needs at least one invoice in the context")
        output = input_ = sales = Money.zero()
        for invoice in ctx.invoices:
            if not isinstance(invoice, Invoice):
                raise InvalidIncomeError("every item in ctx.invoices must be an Invoice")
            net, vat = self.split(invoice)
            if invoice.kind == SALE:
                output, sales = output + vat, sales + net
            else:
                input_ = input_ + vat
        net_payable = output - input_
        label = "net VAT payable" if not net_payable.is_negative() else "net VAT credit (refundable/carried forward)"
        return TaxResult(self.name, sales, net_payable,
                         (("output VAT on sales", output), ("input VAT on purchases", input_), (label, net_payable)))
