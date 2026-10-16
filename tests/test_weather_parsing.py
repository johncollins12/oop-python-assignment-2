"""Offline tests of the parsing functions, using real API responses saved in tests/data/.

The samples were captured once with scripts/save_samples.py, so these tests run
without a network connection.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from a2.weather.errors import (AmbiguousLocationError, InvalidCoordinatesError,
                               LocationNotFoundError, RequestFailedError, WeatherError)
from a2.weather.forecast import WMO_CODES, describe_weather, forecast_to_dataframe, summarise, validate_request
from a2.weather.geocoding import Location, choose_location, geocode, parse_locations
from a2.weather.http import get_json
from a2.weather.metno import metno_to_daily
from conftest import FakeSession, make_response

DATA = Path(__file__).parent / "data"


def sample(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


# ----- geocoding -----------------------------------------------------------------
def test_dresden_best_match_is_in_germany():
    best = parse_locations(sample("geocode_dresden")["body"])[0]
    assert best.name == "Dresden" and best.country == "Germany"
    assert 50.9 < best.latitude < 51.2 and 13.5 < best.longitude < 14.0
    assert best.timezone == "Europe/Berlin"


def test_missing_results_key_means_no_candidates():
    body = sample("geocode_no_results")["body"]
    assert "results" not in body
    assert parse_locations(body) == []
    with pytest.raises(LocationNotFoundError):
        choose_location("Qzxqzxqzx", parse_locations(body))


def test_ambiguous_name_lists_candidates_until_one_is_chosen():
    candidates = parse_locations(sample("geocode_springfield")["body"])
    assert len(candidates) > 1
    with pytest.raises(AmbiguousLocationError) as info:
        choose_location("Springfield", candidates, index=None)
    assert len(info.value.candidates) == len(candidates)
    assert choose_location("Springfield", candidates, index=1) == candidates[1]


def test_out_of_range_candidate_index_is_refused():
    candidates = parse_locations(sample("geocode_springfield")["body"])
    with pytest.raises(AmbiguousLocationError):
        choose_location("Springfield", candidates, index=len(candidates))


def test_malformed_geocoding_result_raises():
    with pytest.raises(WeatherError):
        parse_locations({"results": [{"name": "X"}]})        # no coordinates


def test_geocode_goes_through_the_robust_wrapper():
    session = FakeSession([make_response(200, sample("geocode_dresden")["body"])])
    result = geocode("Dresden", user_agent="ua", session=session)
    assert isinstance(result[0], Location)
    assert session.calls[0]["params"]["name"] == "Dresden"
    assert session.calls[0]["headers"]["User-Agent"] == "ua"


# ----- forecast ----------------------------------------------------------------------
def test_forecast_dataframe_has_units_and_one_row_per_day():
    frame = forecast_to_dataframe(sample("forecast_dresden")["body"])
    assert len(frame) == 7
    assert list(frame.columns) == ["Weather", "Max temp (°C)", "Min temp (°C)",
                                   "Precipitation (mm)", "Max wind (km/h)"]
    assert (frame["Max temp (°C)"] >= frame["Min temp (°C)"]).all()
    assert (frame["Precipitation (mm)"] >= 0).all()
    assert frame.attrs["timezone"] == "Europe/Berlin"


def test_every_weather_code_in_the_sample_is_decoded():
    frame = forecast_to_dataframe(sample("forecast_dresden")["body"])
    assert not frame["Weather"].str.startswith("Unknown").any()


def test_weather_code_decoding():
    assert describe_weather(0) == "Clear sky"
    assert describe_weather(63.0) == "Moderate rain"
    assert describe_weather(42) == "Unknown code 42"
    assert describe_weather(None) == "No data"
    assert len(WMO_CODES) == 28


def test_forecast_with_missing_field_raises():
    body = sample("forecast_dresden")["body"]
    broken = {**body, "daily": {k: v for k, v in body["daily"].items() if k != "precipitation_sum"}}
    with pytest.raises(WeatherError, match="missing"):
        forecast_to_dataframe(broken)


def test_summary_mentions_place_and_attribution():
    frame = forecast_to_dataframe(sample("forecast_dresden")["body"])
    text = summarise(frame, "Dresden, Germany")
    assert text.startswith("Dresden, Germany") and "Open-Meteo.com" in text


@pytest.mark.parametrize("lat, lon, days", [(100, 13, 7), (-91, 0, 7), (51, 200, 7), (51, 13, 0), (51, 13, 17)])
def test_invalid_coordinates_or_days_are_rejected_before_any_request(lat, lon, days):
    with pytest.raises(InvalidCoordinatesError):
        validate_request(lat, lon, days)


def test_server_rejection_of_invalid_latitude_is_not_retried():
    saved = sample("forecast_invalid_latitude")
    assert saved["status"] == 400 and saved["body"]["error"] is True
    session = FakeSession([make_response(400, saved["body"])])
    with pytest.raises(RequestFailedError, match="HTTP 400"):
        get_json("https://api.open-meteo.com/v1/forecast", session=session)
    assert len(session.calls) == 1


# ----- MET Norway ----------------------------------------------------------------------
def test_metno_daily_aggregation_is_consistent():
    daily = metno_to_daily(sample("metno_dresden")["body"], "Europe/Berlin")
    assert len(daily) >= 3
    assert (daily["Max temp (°C)"] >= daily["Min temp (°C)"]).all()
    assert (daily["Precipitation (mm)"].dropna() >= 0).all()
    assert (daily["Max wind (km/h)"] >= 0).all()
    assert (daily["Hours covered"] >= 0).all()
    assert daily["Hours covered"].iloc[1] == 24          # tomorrow is fully covered by hourly steps


def test_metno_wind_is_converted_to_kmh():
    body = {"properties": {"timeseries": [
        {"time": "2026-10-16T10:00:00Z", "data": {"instant": {"details": {"air_temperature": 10.0, "wind_speed": 5.0}}}},
    ]}}
    daily = metno_to_daily(body, "UTC")
    assert daily["Max wind (km/h)"].iloc[0] == pytest.approx(18.0)


def test_metno_empty_series_raises():
    with pytest.raises(WeatherError):
        metno_to_daily({"properties": {"timeseries": []}}, "UTC")
