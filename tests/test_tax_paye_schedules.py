"""PAYE schedules: band-edge boundary tests, URA's own worked example, dates, and properties."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from a2.tax.errors import InvalidIncomeError, NoScheduleForDateError
from a2.tax.money import Money
from a2.tax.schedules import NON_RESIDENT, RESIDENT, URA_PAYE

NEW = URA_PAYE.lookup(RESIDENT, date(2026, 7, 31))
OLD = URA_PAYE.lookup(RESIDENT, date(2026, 6, 30))
NONRES = URA_PAYE.lookup(NON_RESIDENT, date(2026, 7, 31))
ALL = [NEW, OLD, NONRES]


def tax(schedule, income) -> Decimal:
    return schedule.tax(Money(income))[0].amount


# ----- boundary tests at every band edge (resident, from 1 July 2026) -----------------
@pytest.mark.parametrize("income, expected", [
    (335_000, "0"),                     # top of the nil band
    (335_001, "0.20"),                  # first shilling taxed at 20%
    (410_000, "15000"),                 # 20% x 75,000
    (485_000, "33750"),                 # 15,000 + 25% x 75,000
    (10_000_000, "2888250"),            # 33,750 + 30% x 9,515,000
    (10_000_001, "2888250.40"),         # + 30% + 10% surcharge on the last shilling
])
def test_resident_band_edges(income, expected):
    assert tax(NEW, income) == Decimal(expected)


def test_constants_in_the_ura_formulas_are_reproduced():
    # URA states 15,000 at 410,000 and 33,750 at 485,000 (new); 10,000 / 25,000 (old);
    # 33,500 / 48,500 (non-resident).
    assert tax(OLD, 335_000) == 10_000 and tax(OLD, 410_000) == 25_000
    assert tax(NONRES, 335_000) == 33_500 and tax(NONRES, 410_000) == 48_500


def test_ura_worked_example_old_versus_new():
    # URA notice of 7 Sep 2026: on UGX 500,000 the old rate gives 52,000, the new 38,250.
    assert tax(OLD, 500_000) == 52_000
    assert tax(NEW, 500_000) == Decimal("38250")


def test_breakdown_lines_add_up_to_the_total():
    total, lines = NEW.tax(Money(12_000_000))
    assert sum((amount for _, amount in lines), Money.zero()) == total
    assert any("surcharge" in label for label, _ in lines)


# ----- dates and validation --------------------------------------------------------------
def test_schedule_is_chosen_by_date():
    assert URA_PAYE.lookup(RESIDENT, date(2026, 7, 1)).name.endswith("from 1 July 2026")
    assert URA_PAYE.lookup(RESIDENT, date(2026, 6, 30)).name.endswith("FY 2025/26")


def test_date_before_any_schedule_raises():
    with pytest.raises(NoScheduleForDateError):
        URA_PAYE.lookup(RESIDENT, date(2025, 6, 30))


def test_unknown_residency_raises():
    with pytest.raises(NoScheduleForDateError):
        URA_PAYE.lookup("visitor", date(2026, 7, 1))


def test_negative_income_is_refused():
    with pytest.raises(InvalidIncomeError):
        NEW.tax(Money(-1))


# ----- property-based tests (hypothesis) ---------------------------------------------------
incomes = st.decimals(min_value=0, max_value=100_000_000, places=2, allow_nan=False, allow_infinity=False)


@settings(max_examples=300)
@given(income=incomes, schedule=st.sampled_from(ALL))
def test_tax_is_never_negative_and_never_exceeds_income(income, schedule):
    t = tax(schedule, income)
    assert Decimal(0) <= t <= income


@settings(max_examples=300)
@given(a=incomes, b=incomes, schedule=st.sampled_from(ALL))
def test_tax_is_monotonic_in_income(a, b, schedule):
    low, high = sorted((a, b))
    assert tax(schedule, low) <= tax(schedule, high)


@settings(max_examples=300)
@given(a=incomes, b=incomes, schedule=st.sampled_from(ALL))
def test_marginal_rate_never_exceeds_40_percent(a, b, schedule):
    low, high = sorted((a, b))
    assert tax(schedule, high) - tax(schedule, low) <= Decimal("0.40") * (high - low)
