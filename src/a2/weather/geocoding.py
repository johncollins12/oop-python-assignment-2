"""Location name -> coordinates with the Open-Meteo Geocoding API.

Part A: `geocode_urllib` uses only the standard library (urllib.request,
urllib.parse, json). Part B: `geocode` uses requests through the robust `fetch`
wrapper and returns typed `Location` candidates.
"""

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from a2.weather.errors import AmbiguousLocationError, LocationNotFoundError, WeatherError
from a2.weather.http import get_json

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


@dataclass(frozen=True)
class Location:
    """One geocoding candidate."""

    name: str
    latitude: float
    longitude: float
    country: str = ""
    admin1: str = ""
    timezone: str = "auto"
    population: int | None = None

    def __str__(self) -> str:
        region = ", ".join(part for part in (self.admin1, self.country) if part)
        return f"{self.name}, {region} ({self.latitude:.4f}, {self.longitude:.4f})"


def _check_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("location name must be a non-empty string")
    return name.strip()


def geocode_urllib(name: str, count: int = 5, *, user_agent: str, timeout: float = 10.0) -> dict[str, Any]:
    """Part A: geocode with the standard library only.

    Returns {"data": parsed JSON, "status": int, "content_type": str, "seconds": float}.
    """
    query = urllib.parse.urlencode({"name": _check_name(name), "count": count, "language": "en", "format": "json"})
    request = urllib.request.Request(f"{GEOCODING_URL}?{query}", headers={"User-Agent": user_agent})
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"
    return {"data": json.loads(body.decode(charset)), "status": status,
            "content_type": content_type, "seconds": time.perf_counter() - start}


def parse_locations(data: dict[str, Any]) -> list[Location]:
    """Turn a geocoding JSON response into Location objects.

    The API omits the "results" key entirely when nothing matches, so a
    missing key means "no candidates", not an error.
    """
    if not isinstance(data, dict):
        raise WeatherError("geocoding response is not a JSON object")
    candidates = []
    for item in data.get("results", []):
        try:
            candidates.append(Location(
                name=item["name"],
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                country=item.get("country", ""),
                admin1=item.get("admin1", ""),
                timezone=item.get("timezone", "auto"),
                population=item.get("population"),
            ))
        except (KeyError, TypeError, ValueError) as err:
            raise WeatherError(f"malformed geocoding result: {item!r}") from err
    return candidates


def geocode(name: str, count: int = 10, *, user_agent: str, **fetch_kwargs: Any) -> list[Location]:
    """Part B: candidate locations for `name` (possibly an empty list)."""
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")
    params = {"name": _check_name(name), "count": count, "language": "en", "format": "json"}
    data = get_json(GEOCODING_URL, params, headers={"User-Agent": user_agent}, **fetch_kwargs)
    return parse_locations(data)


def choose_location(name: str, candidates: list[Location], index: int | None = 0) -> Location:
    """Pick one candidate.

    index=None means "only accept an unambiguous name": several candidates then
    raise AmbiguousLocationError listing them. An integer picks that candidate
    (0 = the geocoder's best match).
    """
    if not candidates:
        raise LocationNotFoundError(f"No location found for {name!r}")
    if index is None:
        if len(candidates) > 1:
            raise AmbiguousLocationError(name, [str(c) for c in candidates])
        return candidates[0]
    if not 0 <= index < len(candidates):
        raise AmbiguousLocationError(name, [str(c) for c in candidates])
    return candidates[index]
