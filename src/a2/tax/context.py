"""Inputs (TaxContext) and outputs (TaxResult) shared by every tax in the engine."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from a2.tax.errors import InvalidIncomeError
from a2.tax.money import Money
from a2.tax.schedules import NON_RESIDENT, RESIDENT

__all__ = ["TaxContext", "TaxResult"]

_MONEY_FIELDS = ("gross_pay", "allowances", "lst", "revenue", "allowable_deductions")


@dataclass(frozen=True)
class TaxContext:
    """Everything a tax may need. Each tax reads only the fields it uses.

    gross_pay, allowances : monthly employment income (cash allowances are taxable)
    lst                   : Local Service Tax deducted this month (set by the payroll pipeline)
    invoices              : VAT invoices for the period
    revenue, allowable_deductions : company figures for corporate income tax
    """

    on: date
    residency: str = RESIDENT
    gross_pay: Money | None = None
    allowances: Money = field(default_factory=Money.zero)
    lst: Money = field(default_factory=Money.zero)
    invoices: tuple[Any, ...] = ()
    revenue: Money | None = None
    allowable_deductions: Money = field(default_factory=Money.zero)

    def __post_init__(self) -> None:
        if not isinstance(self.on, date):
            raise InvalidIncomeError("`on` must be a datetime.date")
        if self.residency not in (RESIDENT, NON_RESIDENT):
            raise InvalidIncomeError(f"residency must be {RESIDENT!r} or {NON_RESIDENT!r}")
        for name in _MONEY_FIELDS:
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, Money):
                raise InvalidIncomeError(f"{name} must be a Money value, got {type(value).__name__}")
            if value.is_negative():
                raise InvalidIncomeError(f"{name} cannot be negative: {value!r}")

    def require(self, name: str) -> Money:
        """Return a money field, raising InvalidIncomeError if it was not provided."""
        value = getattr(self, name)
        if value is None:
            raise InvalidIncomeError(f"{name} is required for this tax")
        return value

    @property
    def total_gross(self) -> Money:
        """Gross pay plus allowances."""
        return self.require("gross_pay") + self.allowances


@dataclass(frozen=True)
class TaxResult:
    """Outcome of one tax calculation.

    `amount` is rounded half-up to whole shillings; `exact` keeps the unrounded value.
    """

    tax: str
    base: Money
    exact: Money
    lines: tuple[tuple[str, Money], ...] = ()
    schedule: str = ""

    @property
    def amount(self) -> Money:
        return self.exact.rounded()

    def __str__(self) -> str:
        detail = f" [{self.schedule}]" if self.schedule else ""
        return f"{self.tax}: {self.amount} on base {self.base}{detail}"
