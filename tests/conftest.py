"""Shared test helpers: a fake HTTP session so tests never touch the network."""

import json

import pytest
import requests


def make_response(status: int = 200, body=None, url: str = "https://example.test/api") -> requests.Response:
    """Build a real requests.Response object with the given status and JSON body."""
    response = requests.Response()
    response.status_code = status
    response.url = url
    response.reason = {200: "OK", 404: "Not Found", 429: "Too Many Requests",
                       500: "Internal Server Error", 503: "Service Unavailable"}.get(status, "")
    response._content = (body if isinstance(body, bytes) else json.dumps(body or {}).encode())
    response.headers["Content-Type"] = "application/json"
    return response


class FakeSession:
    """Plays back a scripted list of outcomes: Response objects or exceptions to raise."""

    def __init__(self, outcomes: list) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


@pytest.fixture
def sleeps() -> list:
    """Record requested back-off delays instead of actually sleeping."""
    return []
