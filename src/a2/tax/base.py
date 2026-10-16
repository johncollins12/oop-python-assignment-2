"""The abstract base class every tax implements."""

from abc import ABC, abstractmethod

from a2.tax.context import TaxContext, TaxResult


class Tax(ABC):
    """A tax rule: given a context, produce a result. Subclasses must implement `calculate`."""

    name: str = "Tax"

    @abstractmethod
    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Compute this tax for the given context."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
