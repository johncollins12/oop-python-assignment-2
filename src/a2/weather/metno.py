"""Second source: MET Norway Locationforecast 2.0 (compact), aggregated to daily values."""

from typing import Any

import pandas as pd

from a2.weather.errors import WeatherError
from a2.weather.forecast import validate_request
from a2.weather.http import get_json

METNO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
MS_TO_KMH = 3.6


def get_metno(lat: float, lon: float, *, user_agent: str, **fetch_kwargs: Any) -> dict[str, Any]:
    """Compact forecast JSON. Coordinates are rounded to 4 decimals, as MET Norway's terms ask."""
    validate_request(lat, lon, 1)
    params = {"lat": round(lat, 4), "lon": round(lon, 4)}
    return get_json(METNO_URL, params, headers={"User-Agent": user_agent}, **fetch_kwargs)


def metno_to_daily(data: dict[str, Any], timezone: str) -> pd.DataFrame:
    """Aggregate MET Norway's time series to local calendar days.

    The series is hourly for roughly the first two days, then 6-hourly. Each step's
    precipitation is taken from the period that matches the step length
    (next_1_hours for 1-h steps, next_6_hours for 6-h steps), so nothing is counted twice.
    Temperatures are the max/min of the instantaneous values; wind is converted m/s -> km/h.
    Each step is assigned to the local date on which it starts, so a 6-h step starting in
    the evening counts towards that day; "Hours covered" is the precipitation period counted.
    """
    try:
        series = data["properties"]["timeseries"]
        rows = []
        for i, step in enumerate(series):
            t = pd.Timestamp(step["time"])
            details = step["data"]["instant"]["details"]
            gap = (pd.Timestamp(series[i + 1]["time"]) - t) if i + 1 < len(series) else None
            precip = None
            if gap == pd.Timedelta(hours=1) and "next_1_hours" in step["data"]:
                precip = step["data"]["next_1_hours"]["details"].get("precipitation_amount")
            elif gap == pd.Timedelta(hours=6) and "next_6_hours" in step["data"]:
                precip = step["data"]["next_6_hours"]["details"].get("precipitation_amount")
            rows.append({"time": t, "temp": details.get("air_temperature"),
                         "wind": details.get("wind_speed"), "precip": precip,
                         "hours": gap.total_seconds() / 3600 if precip is not None else 0.0})
    except (KeyError, TypeError) as err:
        raise WeatherError(f"MET Norway response is missing expected field: {err}") from err
    if not rows:
        raise WeatherError("MET Norway response has an empty time series")
    frame = pd.DataFrame(rows)
    frame["date"] = frame["time"].dt.tz_convert(timezone).dt.date
    daily = frame.groupby("date").agg(
        temp_max=("temp", "max"), temp_min=("temp", "min"),
        precip=("precip", lambda s: s.sum(min_count=1)), wind_max=("wind", "max"),
        hours_covered=("hours", "sum"))
    daily["wind_max"] = daily["wind_max"] * MS_TO_KMH
    daily.index.name = "Date"
    return daily.rename(columns={"temp_max": "Max temp (°C)", "temp_min": "Min temp (°C)",
                                 "precip": "Precipitation (mm)", "wind_max": "Max wind (km/h)",
                                 "hours_covered": "Hours covered"})
