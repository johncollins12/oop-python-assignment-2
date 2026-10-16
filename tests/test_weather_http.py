"""Tests for a2.weather.http (retries, back-off, errors) and a2.weather.config."""

import pytest
import requests

from a2.weather.config import ENV_VAR, PLACEHOLDER, contact_email, user_agent
from a2.weather.errors import ConfigurationError, RequestFailedError, WeatherError
from a2.weather.http import RetryPolicy, fetch, get_json, is_retryable_status
from conftest import FakeSession, make_response

URL = "https://example.test/api"


# ----- fetch / get_json -----------------------------------------------------------
def test_success_on_first_attempt_passes_params_and_timeout(sleeps):
    session = FakeSession([make_response(200, {"ok": True})])
    data = get_json(URL, {"name": "Dresden"}, session=session, timeout=5, sleep=sleeps.append)
    assert data == {"ok": True}
    assert session.calls[0]["params"] == {"name": "Dresden"}
    assert session.calls[0]["timeout"] == 5
    assert sleeps == []


def test_server_error_is_retried_with_exponential_backoff(sleeps):
    session = FakeSession([make_response(503), make_response(500), make_response(200, {"ok": 1})])
    assert get_json(URL, session=session, sleep=sleeps.append) == {"ok": 1}
    assert len(session.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_connection_errors_exhaust_retries_then_raise_custom_error(sleeps):
    session = FakeSession([requests.ConnectionError("down")] * 4)
    with pytest.raises(RequestFailedError) as info:
        fetch(URL, session=session, sleep=sleeps.append)
    assert info.value.attempts == 4
    assert "connection error" in info.value.reason
    assert sleeps == [0.5, 1.0, 2.0]                 # no sleep after the final attempt


def test_timeout_is_retried(sleeps):
    session = FakeSession([requests.Timeout("slow"), make_response(200, {"ok": 2})])
    assert get_json(URL, session=session, timeout=0.001, sleep=sleeps.append) == {"ok": 2}
    assert sleeps == [0.5]


def test_client_error_is_not_retried(sleeps):
    session = FakeSession([make_response(404)])
    with pytest.raises(RequestFailedError, match="HTTP 404"):
        fetch(URL, session=session, sleep=sleeps.append)
    assert len(session.calls) == 1 and sleeps == []


def test_backoff_is_capped():
    policy = RetryPolicy(max_attempts=10, base_delay=1.0, max_delay=4.0)
    assert [policy.delay(k) for k in range(1, 6)] == [1.0, 2.0, 4.0, 4.0, 4.0]


def test_invalid_json_body_raises_custom_error():
    session = FakeSession([make_response(200, b"<html>not json</html>")])
    with pytest.raises(RequestFailedError, match="not valid JSON"):
        get_json(URL, session=session)


def test_non_positive_timeout_is_rejected():
    with pytest.raises(ValueError):
        fetch(URL, timeout=0, session=FakeSession([]))


@pytest.mark.parametrize("status, expected", [(500, True), (503, True), (429, True), (404, False), (400, False)])
def test_retryable_status_codes(status, expected):
    assert is_retryable_status(status) is expected


def test_custom_errors_share_one_base_class():
    assert issubclass(RequestFailedError, WeatherError)
    assert issubclass(ConfigurationError, WeatherError)


# ----- config ------------------------------------------------------------------------
def test_placeholder_email_is_refused(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    with pytest.raises(ConfigurationError):
        contact_email()
    with pytest.raises(ConfigurationError):
        contact_email(PLACEHOLDER)


def test_email_is_read_from_environment(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "student@university.ac.ug")
    assert contact_email() == "student@university.ac.ug"


def test_malformed_email_is_refused():
    with pytest.raises(ConfigurationError):
        contact_email("not-an-email")


def test_user_agent_identifies_app_and_contact():
    ua = user_agent("student@university.ac.ug")
    assert ua.startswith("oop-python-assignment-2/") and "student@university.ac.ug" in ua
