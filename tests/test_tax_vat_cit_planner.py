"""VAT over invoices, corporate income tax, and the TaxPlanner extension."""

from datetime import date
from decimal import Decimal

import pytest

from a2.tax.cit import CorporateIncomeTax
from a2.tax.context import TaxContext
from a2.tax.errors import InvalidIncomeError
from a2.tax.money import Money
from a2.tax.payroll import NSSF, PAYE, PayrollPipeline
from a2.tax.planner import TaxPlanner
from a2.tax.vat import EXEMPT, PURCHASE, SALE, STANDARD, VAT, ZERO_RATED, Invoice

ON = date(2026, 8, 31)


def vat_ctx(*invoices) -> TaxContext:
    return TaxContext(on=ON, invoices=tuple(invoices))


# ----- VAT ---------------------------------------------------------------------------------
def test_ura_vat_worked_example():
    # URA example: output VAT 270, input VAT 180 -> 90 payable (standard rate 18%).
    result = VAT().calculate(vat_ctx(Invoice("S1", SALE, STANDARD, Money(1_500)),
                                     Invoice("P1", PURCHASE, STANDARD, Money(1_000))))
    assert dict(result.lines)["output VAT on sales"] == Money(270)
    assert dict(result.lines)["input VAT on purchases"] == Money(180)
    assert result.amount == Money(90)


def test_zero_rated_and_exempt_sales_carry_no_output_vat():
    result = VAT().calculate(vat_ctx(Invoice("S1", SALE, ZERO_RATED, Money(5_000)),
                                     Invoice("S2", SALE, EXEMPT, Money(3_000))))
    assert result.amount == Money(0) and result.base == Money(8_000)


def test_zero_rated_seller_gets_a_credit_for_input_vat():
    result = VAT().calculate(vat_ctx(Invoice("S1", SALE, ZERO_RATED, Money(10_000)),     # export
                                     Invoice("P1", PURCHASE, STANDARD, Money(2_000))))
    assert result.amount == Money(-360) and "credit" in result.lines[-1][0]


def test_vat_inclusive_amounts_are_split_correctly():
    net, vat = VAT().split(Invoice("S1", SALE, STANDARD, Money(118_000), vat_inclusive=True))
    assert net.rounded() == Money(100_000) and vat.rounded() == Money(18_000)


def test_invalid_invoices_are_refused():
    with pytest.raises(InvalidIncomeError):
        Invoice("X", "refund", STANDARD, Money(1))
    with pytest.raises(InvalidIncomeError):
        Invoice("X", SALE, "luxury", Money(1))
    with pytest.raises(InvalidIncomeError):
        VAT().calculate(vat_ctx())


# ----- corporate income tax -----------------------------------------------------------------------
def test_cit_on_chargeable_income():
    ctx = TaxContext(on=ON, revenue=Money(500_000_000), allowable_deductions=Money(320_000_000))
    result = CorporateIncomeTax().calculate(ctx)
    assert result.base == Money(180_000_000) and result.amount == Money(54_000_000)


def test_cit_loss_gives_zero_tax_and_reports_the_loss():
    ctx = TaxContext(on=ON, revenue=Money(100), allowable_deductions=Money(250))
    result = CorporateIncomeTax().calculate(ctx)
    assert result.amount == Money(0) and dict(result.lines)["tax loss (carry-forward not modelled)"] == Money(150)


def test_cit_needs_revenue():
    with pytest.raises(InvalidIncomeError):
        CorporateIncomeTax().calculate(TaxContext(on=ON))


# ----- TaxPlanner (extension B) -------------------------------------------------------------------
def test_planner_scenarios_are_internally_consistent():
    planner = TaxPlanner(PayrollPipeline(PAYE(), NSSF()), CorporateIncomeTax())
    comparison = planner.compare(Money(3_300_000), ON)
    for scenario in (comparison.salary, comparison.dividend):
        assert scenario.owner_receives + scenario.total_tax == comparison.profit
    # Dividend route by hand: CIT 990,000; dividend 2,310,000; WHT 15% = 346,500; owner 1,963,500
    assert comparison.dividend.owner_receives == Money(1_963_500)
    assert comparison.difference == (comparison.salary.owner_receives - comparison.dividend.owner_receives
                                     if comparison.better is comparison.salary
                                     else comparison.dividend.owner_receives - comparison.salary.owner_receives)


def test_planner_rejects_non_positive_profit():
    planner = TaxPlanner(PayrollPipeline(PAYE(), NSSF()), CorporateIncomeTax())
    with pytest.raises(InvalidIncomeError):
        planner.compare(Money(0), ON)
