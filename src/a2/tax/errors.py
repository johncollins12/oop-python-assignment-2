"""Exception hierarchy for the tax engine. Every invalid situation raises; nothing fails silently."""


class TaxError(Exception):
    """Base class for all tax-engine errors."""


class InvalidIncomeError(TaxError):
    """An amount is invalid for the calculation (negative income, wrong type, missing field...)."""


class NoScheduleForDateError(TaxError):
    """No tax schedule in the registry covers the requested date and residency."""
