"""Custom exceptions for the weather package.

Every failure the user can meet has its own exception type, all derived from
WeatherError, so a caller can catch one family or one specific case.
"""


class WeatherError(Exception):
    """Base class for every error raised by the weather package."""


class ConfigurationError(WeatherError):
    """The run is not configured correctly (for example, no real contact email)."""


class RequestFailedError(WeatherError):
    """An HTTP request still failed after all permitted attempts."""

    def __init__(self, url: str, attempts: int, reason: str) -> None:
        self.url = url
        self.attempts = attempts
        self.reason = reason
        super().__init__(f"Request to {url} failed after {attempts} attempt(s): {reason}")


class LocationNotFoundError(WeatherError):
    """The geocoder returned no match for a location name."""


class AmbiguousLocationError(WeatherError):
    """A location name matched several places and no choice was made."""

    def __init__(self, name: str, candidates: list) -> None:
        self.name = name
        self.candidates = candidates
        options = "; ".join(f"[{i}] {c}" for i, c in enumerate(candidates))
        super().__init__(
            f"{name!r} matches {len(candidates)} places. Set CANDIDATE_INDEX to one of: {options}"
        )


class InvalidCoordinatesError(WeatherError):
    """Latitude, longitude or the number of days is outside the valid range."""
