"""Tests for the Money value object: Decimal only, explicit rounding, operator overloading."""

from decimal import Decimal

import pytest

from a2.tax.money import Money


def test_float_is_refused_everywhere():
    with pytest.raises(TypeError):
        Money(0.1)
    with pytest.raises(TypeError):
        Money(100) * 0.18


def test_exact_decimal_arithmetic_where_float_fails():
    assert 0.1 + 0.2 != 0.3                                    # the float problem
    assert Money("0.1") + Money("0.2") == Money("0.3")         # exact with Decimal


def test_operators():
    a, b = Money(1_000), Money(250)
    assert a + b == Money(1_250)
    assert a - b == Money(750)
    assert a * Decimal("0.18") == Money(180)
    assert 2 * b == Money(500)
    assert b < a and a > b and a >= Money(1_000)


def test_half_up_rounding_to_whole_shillings():
    assert Money("2.5").rounded() == Money(3)
    assert Money("2.4999").rounded() == Money(2)
    assert Money("-2.5").rounded() == Money(-3)               # half away from zero


def test_repr_and_str():
    assert repr(Money("1234.5")) == "Money('1234.5', 'UGX')"
    assert str(Money("1234.5")) == "UGX 1,235"


def test_money_is_immutable_and_hashable():
    m = Money(5)
    with pytest.raises(AttributeError):
        m._amount = Decimal(6)
    assert len({Money(5), Money("5.0")}) == 1


@pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity", None, [1]])
def test_invalid_amounts_are_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        Money(bad)


def test_money_times_money_is_not_allowed():
    with pytest.raises(TypeError):
        Money(2) * Money(3)
