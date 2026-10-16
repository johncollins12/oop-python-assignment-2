"""Progressive PAYE schedules with effective dates, and a registry that picks the right one.

Sources (see the notebook for full citations)
--------------------------------------------
* Resident, from 1 July 2026: URA public notice "Changes to PAYE return form following the
  Income Tax (Amendment) Act, 2026" (7 September 2026); Act assented 20 August 2026,
  effective 1 July 2026.
* Resident FY 2025/26 and non-resident: URA PAYE rates page (ura.go.ug).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from a2.tax.errors import InvalidIncomeError, NoScheduleForDateError
from a2.tax.money import Money

__all__ = ["Band", "ProgressiveSchedule", "ScheduleRegistry", "URA_PAYE", "RESIDENT", "NON_RESIDENT"]

RESIDENT = "resident"
NON_RESIDENT = "non-resident"


@dataclass(frozen=True)
class Band:
    """Income above `lower` and up to `upper` (None = no upper limit) is taxed at `rate`."""

    lower: Money
    upper: Money | None
    rate: Decimal

    def __post_init__(self) -> None:
        if self.upper is not None and not self.lower < self.upper:
            raise ValueError("band upper limit must exceed its lower limit")
        if not Decimal(0) <= self.rate <= Decimal(1):
            raise ValueError("rate must be between 0 and 1")

    def taxable_part(self, income: Money) -> Money:
        """Portion of `income` that falls inside this band."""
        top = income if self.upper is None or income < self.upper else self.upper
        return top - self.lower if self.lower < top else Money.zero()


@dataclass(frozen=True)
class ProgressiveSchedule:
    """A monthly progressive schedule, valid from `effective_from` to `effective_to` (inclusive)."""

    name: str
    residency: str
    effective_from: date
    effective_to: date | None
    bands: tuple[Band, ...]
    surcharge_threshold: Money | None = None
    surcharge_rate: Decimal = Decimal(0)
    source: str = ""

    def __post_init__(self) -> None:
        if not self.bands or self.bands[0].lower != Money.zero():
            raise ValueError("bands must start at zero")
        for prev, nxt in zip(self.bands, self.bands[1:]):
            if prev.upper != nxt.lower:
                raise ValueError("bands must be contiguous")
        if self.bands[-1].upper is not None:
            raise ValueError("the last band must have no upper limit")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to is before effective_from")

    def covers(self, on: date) -> bool:
        return self.effective_from <= on and (self.effective_to is None or on <= self.effective_to)

    def tax(self, income: Money) -> tuple[Money, list[tuple[str, Money]]]:
        """Exact (unrounded) tax on monthly chargeable `income`, with a per-band breakdown."""
        if not isinstance(income, Money):
            raise InvalidIncomeError("income must be a Money value")
        if income.is_negative():
            raise InvalidIncomeError(f"chargeable income cannot be negative: {income!r}")
        lines, total = [], Money.zero()
        for band in self.bands:
            part = band.taxable_part(income)
            if part > Money.zero() and band.rate > 0:
                amount = part * band.rate
                where = (f"above {band.lower.amount:,.0f}" if band.upper is None
                         else f"on {band.lower.amount:,.0f}–{band.upper.amount:,.0f}")
                lines.append((f"{band.rate:.0%} {where}", amount))
                total = total + amount
        if self.surcharge_threshold is not None and self.surcharge_threshold < income:
            amount = (income - self.surcharge_threshold) * self.surcharge_rate
            lines.append((f"{self.surcharge_rate:.0%} surcharge above {self.surcharge_threshold.amount:,.0f}", amount))
            total = total + amount
        return total, lines


@dataclass
class ScheduleRegistry:
    """Holds dated schedules and returns the one in force for a residency on a date."""

    schedules: list[ProgressiveSchedule] = field(default_factory=list)

    def add(self, schedule: ProgressiveSchedule) -> None:
        for existing in self.schedules:
            if existing.residency == schedule.residency and _overlap(existing, schedule):
                raise ValueError(f"{schedule.name!r} overlaps {existing.name!r}")
        self.schedules.append(schedule)

    def lookup(self, residency: str, on: date) -> ProgressiveSchedule:
        for schedule in self.schedules:
            if schedule.residency == residency and schedule.covers(on):
                return schedule
        raise NoScheduleForDateError(f"no {residency} PAYE schedule covers {on.isoformat()}")


def _overlap(a: ProgressiveSchedule, b: ProgressiveSchedule) -> bool:
    a_end = a.effective_to or date.max
    b_end = b.effective_to or date.max
    return a.effective_from <= b_end and b.effective_from <= a_end


def _bands(edges: Iterable[tuple[int, str]]) -> tuple[Band, ...]:
    """Build contiguous bands from (lower limit, rate) pairs."""
    pairs = list(edges)
    return tuple(
        Band(Money(lo), Money(pairs[i + 1][0]) if i + 1 < len(pairs) else None, Decimal(rate))
        for i, (lo, rate) in enumerate(pairs)
    )


URA_PAYE = ScheduleRegistry()
URA_PAYE.add(ProgressiveSchedule(
    name="Resident PAYE, FY 2025/26", residency=RESIDENT,
    effective_from=date(2025, 7, 1), effective_to=date(2026, 6, 30),
    bands=_bands([(0, "0"), (235_000, "0.10"), (335_000, "0.20"), (410_000, "0.30")]),
    surcharge_threshold=Money(10_000_000), surcharge_rate=Decimal("0.10"),
    source="URA PAYE rates page (ura.go.ug), FY 2025/26 resident schedule"))
URA_PAYE.add(ProgressiveSchedule(
    name="Resident PAYE, from 1 July 2026", residency=RESIDENT,
    effective_from=date(2026, 7, 1), effective_to=None,
    bands=_bands([(0, "0"), (335_000, "0.20"), (410_000, "0.25"), (485_000, "0.30")]),
    surcharge_threshold=Money(10_000_000), surcharge_rate=Decimal("0.10"),
    source="URA notice, Income Tax (Amendment) Act 2026, effective 1 July 2026 (published 7 Sep 2026)"))
URA_PAYE.add(ProgressiveSchedule(
    name="Non-resident PAYE", residency=NON_RESIDENT,
    effective_from=date(2025, 7, 1), effective_to=None,
    bands=_bands([(0, "0.10"), (335_000, "0.20"), (410_000, "0.30")]),
    surcharge_threshold=Money(10_000_000), surcharge_rate=Decimal("0.10"),
    source="URA PAYE rates page (ura.go.ug); not changed by the 2026 amendment notice (resident only)"))
