"""PAYE via TaxContext, NSSF, Local Service Tax and the payroll pipeline."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from a2.tax.base import Tax
from a2.tax.context import TaxContext
from a2.tax.errors import InvalidIncomeError, NoScheduleForDateError
from a2.tax.money import Money
from a2.tax.payroll import NSSF, PAYE, LocalServiceTax, PayrollPipeline
from a2.tax.schedules import NON_RESIDENT

AUG_2026 = date(2026, 8, 31)


def ctx(gross, allowances=0, on=AUG_2026, **kw) -> TaxContext:
    return TaxContext(on=on, gross_pay=Money(gross), allowances=Money(allowances), **kw)


def test_tax_base_class_is_abstract():
    with pytest.raises(TypeError):
        Tax()


# ----- PAYE --------------------------------------------------------------------------------
def test_paye_matches_ura_example_and_includes_allowances():
    assert PAYE().calculate(ctx(500_000)).amount == Money(38_250)
    # 600,000 chargeable: 33,750 + 30% x 115,000 = 68,250
    assert PAYE().calculate(ctx(500_000, allowances=100_000)).amount == Money(68_250)


def test_paye_uses_the_schedule_in_force_on_the_pay_date():
    assert PAYE().calculate(ctx(500_000, on=date(2026, 6, 30))).amount == Money(52_000)


def test_non_resident_schedule():
    result = PAYE().calculate(ctx(300_000, residency=NON_RESIDENT))
    assert result.amount == Money(30_000) and "Non-resident" in result.schedule


def test_result_is_rounded_half_up_but_exact_value_is_kept():
    result = PAYE().calculate(ctx(335_003))                 # 20% x 3 = 0.6
    assert result.exact == Money("0.60") and result.amount == Money(1)


def test_missing_or_invalid_income_is_refused():
    with pytest.raises(InvalidIncomeError):
        PAYE().calculate(TaxContext(on=AUG_2026))
    with pytest.raises(InvalidIncomeError):
        ctx(-1)
    with pytest.raises(InvalidIncomeError):
        TaxContext(on=AUG_2026, gross_pay=500_000)          # plain int, not Money
    with pytest.raises(InvalidIncomeError):
        TaxContext(on=AUG_2026, gross_pay=Money(1), residency="tourist")


def test_pay_date_without_a_schedule_raises():
    with pytest.raises(NoScheduleForDateError):
        PAYE().calculate(ctx(500_000, on=date(2020, 1, 31)))


# ----- NSSF and LST --------------------------------------------------------------------------
def test_nssf_employee_and_employer_shares():
    nssf = NSSF()
    assert nssf.calculate(ctx(1_000_000)).amount == Money(50_000)
    assert nssf.employer(ctx(1_000_000)) == Money(100_000)


def test_lst_is_spread_over_the_instalment_months_only():
    lst = LocalServiceTax(Money(100_000))
    assert lst.calculate(ctx(1, on=date(2026, 8, 1))).amount == Money(25_000)
    assert lst.calculate(ctx(1, on=date(2026, 11, 1))).amount == Money(0)


def test_lst_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        LocalServiceTax(Money(100_000), instalment_months=(13,))
    with pytest.raises(InvalidIncomeError):
        LocalServiceTax(Money(-1))


# ----- pipeline ---------------------------------------------------------------------------------
def test_payroll_pipeline_hand_calculation():
    # gross 1,000,000 + allowances 200,000 = 1,200,000; August -> LST 60,000 / 4 = 15,000
    # NSSF 5% x 1,200,000 = 60,000; chargeable = 1,200,000 - 15,000 = 1,185,000
    # PAYE = 33,750 + 30% x (1,185,000 - 485,000) = 243,750
    # net = 1,200,000 - 60,000 - 15,000 - 243,750 = 881,250
    slip = PayrollPipeline(PAYE(), NSSF(), LocalServiceTax(Money(60_000))).run(ctx(1_000_000, 200_000))
    assert slip.nssf_employee == Money(60_000)
    assert slip.lst == Money(15_000)
    assert slip.chargeable_income == Money(1_185_000)
    assert slip.paye == Money(243_750)
    assert slip.net_pay == Money(881_250)
    assert slip.nssf_employer == Money(120_000)


def test_nssf_deductible_switch_changes_chargeable_income():
    plain = PAYE().chargeable_income(ctx(1_000_000))
    deductible = PAYE(nssf_deductible=True).chargeable_income(ctx(1_000_000))
    assert plain - deductible == Money(50_000)


def test_lst_larger_than_pay_is_refused_not_hidden():
    # Found by hypothesis: a fixed LST instalment on a near-zero salary would make net pay negative.
    with pytest.raises(InvalidIncomeError, match="exceed"):
        PayrollPipeline(PAYE(), NSSF(), LocalServiceTax(Money(100_000))).run(ctx(10_000))


@settings(max_examples=200)
@given(gross=st.integers(min_value=100_000, max_value=60_000_000), allowances=st.integers(0, 5_000_000))
def test_payslip_always_balances(gross, allowances):
    slip = PayrollPipeline(PAYE(), NSSF(), LocalServiceTax(Money(100_000))).run(ctx(gross, allowances))
    assert slip.net_pay + slip.nssf_employee + slip.lst + slip.paye == slip.total_gross
    assert Money.zero() <= slip.paye <= slip.chargeable_income
