"""Tests for the response cache extension (a2.weather.cache) and its use in get_json."""

import pytest

from a2.weather.cache import ResponseCache, expiry_from_headers
from a2.weather.http import get_json
from conftest import FakeSession, make_response

URL = "https://example.test/api"


class Clock:
    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def test_second_identical_request_is_served_from_cache(tmp_path):
    cache = ResponseCache(tmp_path)
    session = FakeSession([make_response(200, {"n": 1})])           # only ONE response available
    first = get_json(URL, {"q": "x"}, cache=cache, session=session)
    second = get_json(URL, {"q": "x"}, cache=cache, session=session)
    assert first == second == {"n": 1}
    assert len(session.calls) == 1 and cache.hits == 1


def test_different_parameters_are_separate_entries(tmp_path):
    cache = ResponseCache(tmp_path)
    session = FakeSession([make_response(200, {"n": 1}), make_response(200, {"n": 2})])
    assert get_json(URL, {"q": "a"}, cache=cache, session=session) == {"n": 1}
    assert get_json(URL, {"q": "b"}, cache=cache, session=session) == {"n": 2}


def test_entries_expire(tmp_path):
    clock = Clock()
    cache = ResponseCache(tmp_path, default_ttl=60, clock=clock)
    cache.put(URL, None, {"n": 1})
    assert cache.get(URL, None) == {"n": 1}
    clock.t += 61
    assert cache.get(URL, None) is None


def test_expires_header_is_honoured():
    now = 1_700_000_000.0
    header = {"Expires": "Tue, 14 Nov 2023 23:13:20 GMT"}            # = now + 3600 s
    assert expiry_from_headers(header, now, 60) == pytest.approx(now + 3600)
    assert expiry_from_headers({"Expires": "not a date"}, now, 60) == now + 60
    assert expiry_from_headers({}, now, 60) == now + 60


def test_clear_removes_entries(tmp_path):
    cache = ResponseCache(tmp_path)
    cache.put(URL, {"a": 1}, {}); cache.put(URL, {"a": 2}, {})
    assert cache.clear() == 2 and cache.get(URL, {"a": 1}) is None
