"""Employment taxes (PAYE, NSSF, Local Service Tax) and the payroll pipeline that combines them.

Order of deductions (see PayrollPipeline.run):
  1. NSSF   on total gross pay. A statutory contribution that does not depend on income tax.
  2. LST    this month's Local Service Tax instalment. Applied before PAYE, as in the brief's baseline.
  3. PAYE   on chargeable income = total gross - LST (employee NSSF is NOT deductible by default).
  4. Net pay = total gross - employee NSSF - LST - PAYE. Employer NSSF is a cost, not a deduction.
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from a2.tax.base import Tax
from a2.tax.context import TaxContext, TaxResult
from a2.tax.errors import InvalidIncomeError
from a2.tax.money import Money
from a2.tax.schedules import URA_PAYE, ScheduleRegistry

__all__ = ["PAYE", "NSSF", "LocalServiceTax", "Payslip", "PayrollPipeline"]


class NSSF(Tax):
    """National Social Security Fund contributions on total gross pay (5% employee, 10% employer)."""

    name = "NSSF"

    def __init__(self, employee_rate: Decimal = Decimal("0.05"), employer_rate: Decimal = Decimal("0.10")) -> None:
        for rate in (employee_rate, employer_rate):
            if not isinstance(rate, Decimal) or not Decimal(0) <= rate <= Decimal(1):
                raise ValueError("NSSF rates must be Decimals between 0 and 1")
        self.employee_rate, self.employer_rate = employee_rate, employer_rate

    def __repr__(self) -> str:
        return f"NSSF(employee_rate={self.employee_rate}, employer_rate={self.employer_rate})"

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """The employee contribution; the employer share is reported in the breakdown."""
        base = ctx.total_gross
        employee, employer = base * self.employee_rate, base * self.employer_rate
        return TaxResult(self.name, base, employee,
                         ((f"employee {self.employee_rate:.0%}", employee),
                          (f"employer {self.employer_rate:.0%} (cost to employer)", employer)))

    def employer(self, ctx: TaxContext) -> Money:
        return (ctx.total_gross * self.employer_rate).rounded()


class LocalServiceTax(Tax):
    """Configurable Local Service Tax: an annual amount collected in equal monthly instalments.

    By default the instalments fall in the first four months of the financial year
    (July-October); in other months the deduction is zero.
    """

    name = "Local Service Tax"

    def __init__(self, annual_amount: Money, instalment_months: tuple[int, ...] = (7, 8, 9, 10)) -> None:
        if not isinstance(annual_amount, Money) or annual_amount.is_negative():
            raise InvalidIncomeError("annual LST must be a non-negative Money value")
        if not instalment_months or any(m not in range(1, 13) for m in instalment_months) \
                or len(set(instalment_months)) != len(instalment_months):
            raise ValueError("instalment_months must be distinct month numbers 1-12")
        self.annual_amount, self.instalment_months = annual_amount, tuple(instalment_months)

    def __repr__(self) -> str:
        return f"LocalServiceTax(annual_amount={self.annual_amount!r}, instalment_months={self.instalment_months})"

    def calculate(self, ctx: TaxContext) -> TaxResult:
        if ctx.on.month in self.instalment_months:
            instalment = Money(self.annual_amount.amount / Decimal(len(self.instalment_months)))
            label = f"instalment {self.instalment_months.index(ctx.on.month) + 1} of {len(self.instalment_months)}"
        else:
            instalment, label = Money.zero(), "no instalment this month"
        return TaxResult(self.name, self.annual_amount, instalment, ((label, instalment),))


class PAYE(Tax):
    """Pay As You Earn on monthly chargeable employment income.

    The schedule is chosen by residency and pay date from a ScheduleRegistry, so resident and
    non-resident rules (and rate changes over time) are data, not separate classes.
    """

    name = "PAYE"

    def __init__(self, registry: ScheduleRegistry = URA_PAYE, *, lst_deductible: bool = True,
                 nssf_deductible: bool = False, nssf_rate: Decimal = Decimal("0.05")) -> None:
        self.registry = registry
        self.lst_deductible = lst_deductible
        self.nssf_deductible = nssf_deductible
        self.nssf_rate = nssf_rate

    def __repr__(self) -> str:
        return f"PAYE(lst_deductible={self.lst_deductible}, nssf_deductible={self.nssf_deductible})"

    def chargeable_income(self, ctx: TaxContext) -> Money:
        income = ctx.total_gross
        if self.lst_deductible:
            income = income - ctx.lst
        if self.nssf_deductible:
            income = income - ctx.total_gross * self.nssf_rate
        return income if not income.is_negative() else Money.zero()

    def calculate(self, ctx: TaxContext) -> TaxResult:
        schedule = self.registry.lookup(ctx.residency, ctx.on)
        chargeable = self.chargeable_income(ctx)
        exact, lines = schedule.tax(chargeable)
        return TaxResult(self.name, chargeable, exact, tuple(lines), schedule.name)


@dataclass(frozen=True)
class Payslip:
    """One month's pay, deductions and employer cost."""

    total_gross: Money
    nssf_employee: Money
    nssf_employer: Money
    lst: Money
    chargeable_income: Money
    paye: Money
    net_pay: Money
    schedule: str

    def rows(self) -> list[tuple[str, Money]]:
        return [("Total gross pay (incl. allowances)", self.total_gross),
                ("less NSSF (employee 5%)", self.nssf_employee),
                ("less Local Service Tax", self.lst),
                ("Chargeable income for PAYE", self.chargeable_income),
                ("less PAYE", self.paye),
                ("Net pay", self.net_pay),
                ("Employer NSSF (10%, cost to employer)", self.nssf_employer)]


class PayrollPipeline:
    """Composes NSSF, Local Service Tax and PAYE in a documented order (see module docstring)."""

    def __init__(self, paye: PAYE, nssf: NSSF, lst: LocalServiceTax | None = None) -> None:
        self.paye, self.nssf, self.lst = paye, nssf, lst

    def __repr__(self) -> str:
        return f"PayrollPipeline({self.paye!r}, {self.nssf!r}, {self.lst!r})"

    def run(self, ctx: TaxContext) -> Payslip:
        nssf = self.nssf.calculate(ctx).amount                                   # 1. NSSF on gross
        lst = self.lst.calculate(ctx).amount if self.lst else Money.zero()       # 2. LST instalment
        paye_result = self.paye.calculate(replace(ctx, lst=lst))                 # 3. PAYE after LST
        paye = paye_result.amount
        net = ctx.total_gross - nssf - lst - paye                                # 4. net pay
        if net.is_negative():
            raise InvalidIncomeError("deductions exceed gross pay; check the inputs")
        return Payslip(ctx.total_gross, nssf, self.nssf.employer(ctx), lst,
                       paye_result.base, paye, net, paye_result.schedule)
