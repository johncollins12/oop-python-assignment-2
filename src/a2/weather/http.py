"""One robust function for every HTTP request in Mini-Project 1.

`fetch` sets a timeout, calls raise_for_status(), retries transient failures
(connection errors, timeouts, HTTP 429 and 5xx) with capped exponential
backoff, and raises RequestFailedError when it finally gives up.

The `session` and `sleep` arguments are injectable: tests and the notebook's
"no network" demonstration pass in fakes, so no real outage or real waiting is needed.
"""

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import requests

from a2.weather.errors import RequestFailedError

__all__ = ["RetryPolicy", "fetch", "get_json", "is_retryable_status"]


@dataclass(frozen=True)
class RetryPolicy:
    """How many times to try, and how long to wait between attempts.

    Delay before retry k (k = 1, 2, ...) = min(max_delay, base_delay * 2**(k - 1)).
    """

    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("delays must not be negative")

    def delay(self, retry_number: int) -> float:
        """Seconds to wait before the given retry (1 = first retry)."""
        return min(self.max_delay, self.base_delay * 2 ** (retry_number - 1))


def is_retryable_status(status: int) -> bool:
    """Server errors (5xx) and 429 Too Many Requests are worth retrying; other 4xx are not."""
    return status == 429 or 500 <= status <= 599


def fetch(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
    policy: RetryPolicy = RetryPolicy(),
    session: Any = None,
    sleep: Callable[[float], None] = time.sleep,
) -> requests.Response:
    """GET `url` with a timeout, status check and retries; return the successful Response.

    Raises
    ------
    ValueError
        If `timeout` is not positive.
    RequestFailedError
        On a non-retryable HTTP error (e.g. 400, 404) immediately, or after
        `policy.max_attempts` attempts for retryable failures.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    client = session if session is not None else requests
    last_reason = "no attempt made"
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = client.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.HTTPError as err:
            status = err.response.status_code if err.response is not None else 0
            last_reason = f"HTTP {status}"
            if not is_retryable_status(status):
                raise RequestFailedError(url, attempt, last_reason) from err
        except requests.Timeout as err:
            last_reason = f"timed out after {timeout} s ({type(err).__name__})"
        except requests.ConnectionError as err:
            last_reason = f"connection error ({type(err).__name__})"
        if attempt < policy.max_attempts:
            sleep(policy.delay(attempt))
    raise RequestFailedError(url, policy.max_attempts, last_reason)


def get_json(url: str, params: Mapping[str, Any] | None = None, *, cache: Any = None,
             **kwargs: Any) -> Any:
    """`fetch` and decode the JSON body; a body that is not JSON raises RequestFailedError.

    If a `cache` (a ResponseCache) is given, a fresh cached body is returned without any
    request, and a new response is stored until its Expires time (or the cache's default TTL).
    """
    if cache is not None:
        cached = cache.get(url, params)
        if cached is not None:
            return cached
    response = fetch(url, params, **kwargs)
    try:
        body = response.json()
    except ValueError as err:
        raise RequestFailedError(url, 1, "response body is not valid JSON") from err
    if cache is not None:
        cache.put(url, params, body, response.headers)
    return body
