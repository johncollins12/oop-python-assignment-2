"""Money value object in Uganda shillings, built on decimal.Decimal only.

Rules
-----
* Floats are refused: Money(0.1) raises TypeError. Use int, str or Decimal.
* Arithmetic is exact: amounts are not rounded during a calculation.
* Rounding is explicit: `rounded()` rounds half-up to whole shillings, the
  convention used for the final amount of every tax result.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering

__all__ = ["Money", "to_decimal"]

CURRENCY = "UGX"
SHILLING = Decimal("1")


def to_decimal(value: object) -> Decimal:
    """Convert int, str or Decimal to a finite Decimal; floats and bools are refused."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{type(value).__name__} is not allowed for money; use int, str or Decimal")
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        try:
            result = Decimal(value)
        except InvalidOperation:
            raise ValueError(f"{value!r} is not a number") from None
    else:
        raise TypeError(f"cannot convert {type(value).__name__} to a money amount")
    if not result.is_finite():
        raise ValueError("money amounts must be finite")
    return result


@total_ordering
class Money:
    """An immutable amount of Uganda shillings."""

    __slots__ = ("_amount",)

    def __init__(self, amount: int | str | Decimal = 0) -> None:
        object.__setattr__(self, "_amount", to_decimal(amount))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Money is immutable")

    # ----- access and rounding -------------------------------------------------
    @property
    def amount(self) -> Decimal:
        return self._amount

    @classmethod
    def zero(cls) -> "Money":
        return cls(0)

    def rounded(self) -> "Money":
        """Round half-up to whole shillings (e.g. 0.5 -> 1, 2.4 -> 2)."""
        return Money(self._amount.quantize(SHILLING, rounding=ROUND_HALF_UP))

    def is_negative(self) -> bool:
        return self._amount < 0

    # ----- arithmetic ------------------------------------------------------------
    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self._amount + other._amount)

    def __sub__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self._amount - other._amount)

    def __neg__(self) -> "Money":
        return Money(-self._amount)

    def __mul__(self, factor: int | Decimal) -> "Money":
        """Money x number (e.g. a tax rate). Money x Money and Money x float are refused."""
        if isinstance(factor, Money):
            return NotImplemented
        if isinstance(factor, float) or isinstance(factor, bool):
            raise TypeError("multiply money by an int or Decimal, never a float")
        if not isinstance(factor, (int, Decimal)):
            return NotImplemented
        return Money(self._amount * factor)

    __rmul__ = __mul__

    # ----- comparison ---------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Money) and self._amount == other._amount

    def __lt__(self, other: "Money") -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self._amount < other._amount

    def __hash__(self) -> int:
        return hash((CURRENCY, self._amount))

    # ----- display --------------------------------------------------------------------
    def __repr__(self) -> str:
        return f"Money('{self._amount}', '{CURRENCY}')"

    def __str__(self) -> str:
        whole = self.rounded().amount
        return f"{CURRENCY} {whole:,.0f}"
