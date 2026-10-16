"""Daily forecast from the Open-Meteo Forecast API, as a tidy pandas DataFrame."""

from typing import Any

import pandas as pd

from a2.weather.errors import InvalidCoordinatesError, WeatherError
from a2.weather.http import get_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_VARIABLES = ("weather_code", "temperature_2m_max", "temperature_2m_min",
                   "precipitation_sum", "wind_speed_10m_max")

# WMO weather interpretation codes, as listed in the Open-Meteo documentation.
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def describe_weather(code: Any) -> str:
    """Readable description of a WMO code; unknown or missing codes are labelled, never hidden."""
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return "No data"
    try:
        return WMO_CODES.get(int(code), f"Unknown code {int(code)}")
    except (TypeError, ValueError):
        return f"Unknown code {code!r}"


def validate_request(lat: float, lon: float, days: int) -> None:
    """Reject coordinates or horizons the API cannot serve, before any request is sent."""
    if not -90 <= lat <= 90:
        raise InvalidCoordinatesError(f"latitude {lat} is outside -90..90")
    if not -180 <= lon <= 180:
        raise InvalidCoordinatesError(f"longitude {lon} is outside -180..180")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 16:
        raise InvalidCoordinatesError(f"days must be an integer from 1 to 16, got {days!r}")


def get_forecast(lat: float, lon: float, days: int = 7, *, user_agent: str,
                 timezone: str = "auto", **fetch_kwargs: Any) -> dict[str, Any]:
    """Daily forecast JSON for (lat, lon): max/min temperature, precipitation, max wind, weather code.

    `timezone` is sent so that the dates are local dates at the location.
    """
    validate_request(lat, lon, days)
    params = {"latitude": lat, "longitude": lon, "daily": ",".join(DAILY_VARIABLES),
              "timezone": timezone, "forecast_days": days}
    return get_json(FORECAST_URL, params, headers={"User-Agent": user_agent}, **fetch_kwargs)


def forecast_to_dataframe(data: dict[str, Any]) -> pd.DataFrame:
    """Convert forecast JSON into a DataFrame with readable column names that carry their units."""
    try:
        daily, units = data["daily"], data["daily_units"]
        dates = pd.to_datetime(daily["time"]).date
        columns = {
            "Weather": [describe_weather(c) for c in daily["weather_code"]],
            f"Max temp ({units['temperature_2m_max']})": daily["temperature_2m_max"],
            f"Min temp ({units['temperature_2m_min']})": daily["temperature_2m_min"],
            f"Precipitation ({units['precipitation_sum']})": daily["precipitation_sum"],
            f"Max wind ({units['wind_speed_10m_max']})": daily["wind_speed_10m_max"],
        }
    except (KeyError, TypeError) as err:
        raise WeatherError(f"forecast response is missing expected field: {err}") from err
    lengths = {len(v) for v in columns.values()} | {len(dates)}
    if len(lengths) != 1:
        raise WeatherError("forecast arrays have different lengths")
    frame = pd.DataFrame(columns, index=pd.Index(dates, name="Date"))
    frame.attrs["timezone"] = data.get("timezone", "")
    return frame


def summarise(frame: pd.DataFrame, place: str) -> str:
    """One-paragraph text summary of a forecast DataFrame."""
    tmax = next(c for c in frame.columns if c.startswith("Max temp"))
    tmin = next(c for c in frame.columns if c.startswith("Min temp"))
    rain = next(c for c in frame.columns if c.startswith("Precipitation"))
    unit_t = tmax[tmax.index("(") + 1:-1]
    unit_p = rain[rain.index("(") + 1:-1]
    wettest = frame[rain].idxmax()
    return (f"{place}, {frame.index[0]} to {frame.index[-1]} ({len(frame)} days, {frame.attrs.get('timezone', '')}): "
            f"highs {frame[tmax].min():.1f}–{frame[tmax].max():.1f} {unit_t}, lows {frame[tmin].min():.1f}–"
            f"{frame[tmin].max():.1f} {unit_t}; total precipitation {frame[rain].sum():.1f} {unit_p}, "
            f"wettest day {wettest} ({frame.loc[wettest, rain]:.1f} {unit_p}, {frame.loc[wettest, 'Weather'].lower()}). "
            "Weather data by Open-Meteo.com (CC BY 4.0).")
