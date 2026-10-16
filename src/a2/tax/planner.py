"""Extension B: TaxPlanner compares paying an owner-manager by salary or by dividend.

For one month, a company has `profit` available before paying its owner.

* Salary route: the company pays salary S and employer NSSF (10%), both deductible, so
  S + 10% S = profit and no corporate tax arises on that profit. The owner then bears
  employee NSSF, Local Service Tax and PAYE through the payroll pipeline.
* Dividend route: the company pays corporate income tax on the profit and distributes
  the rest as a dividend; withholding tax on the dividend is treated as a final tax.

Simplifications are stated in the notebook (monthly basis, no other income, no carry-forward).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from a2.tax.cit import CorporateIncomeTax
from a2.tax.context import TaxContext
from a2.tax.errors import InvalidIncomeError
from a2.tax.money import Money
from a2.tax.payroll import PayrollPipeline

__all__ = ["Scenario", "PlanComparison", "TaxPlanner"]


@dataclass(frozen=True)
class Scenario:
    name: str
    taxes: tuple[tuple[str, Money], ...]
    owner_receives: Money

    @property
    def total_tax(self) -> Money:
        return sum((amount for _, amount in self.taxes), Money.zero())


@dataclass(frozen=True)
class PlanComparison:
    profit: Money
    salary: Scenario
    dividend: Scenario

    @property
    def better(self) -> Scenario:
        return self.salary if self.dividend.owner_receives < self.salary.owner_receives else self.dividend

    @property
    def difference(self) -> Money:
        """How much more the owner receives under the better route."""
        a, b = self.salary.owner_receives, self.dividend.owner_receives
        return a - b if b < a else b - a


class TaxPlanner:
    """Compares two ways of paying out the same pre-tax profit, using existing tax objects (composition)."""

    def __init__(self, pipeline: PayrollPipeline, cit: CorporateIncomeTax,
                 dividend_wht_rate: Decimal = Decimal("0.15")) -> None:
        if not isinstance(dividend_wht_rate, Decimal) or not Decimal(0) <= dividend_wht_rate < Decimal(1):
            raise ValueError("dividend_wht_rate must be a Decimal between 0 and 1")
        self.pipeline, self.cit, self.dividend_wht_rate = pipeline, cit, dividend_wht_rate

    def compare(self, profit: Money, on: date) -> PlanComparison:
        if not isinstance(profit, Money) or not Money.zero() < profit:
            raise InvalidIncomeError("profit must be a positive Money value")
        employer_rate = self.pipeline.nssf.employer_rate
        salary_amount = Money(profit.amount / (Decimal(1) + employer_rate)).rounded()
        slip = self.pipeline.run(TaxContext(on=on, gross_pay=salary_amount))
        employer_nssf = profit - salary_amount
        salary = Scenario("Salary", (("employer NSSF", employer_nssf), ("employee NSSF", slip.nssf_employee),
                                     ("Local Service Tax", slip.lst), ("PAYE", slip.paye)), slip.net_pay)

        cit = self.cit.calculate(TaxContext(on=on, revenue=profit)).amount
        dividend_paid = profit - cit
        wht = (dividend_paid * self.dividend_wht_rate).rounded()
        dividend = Scenario("Dividend", (("corporate income tax", cit), ("dividend withholding tax", wht)),
                            dividend_paid - wht)
        return PlanComparison(profit, salary, dividend)
