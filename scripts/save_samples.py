"""Capture real API responses as sample JSON for the offline tests (run once).

Needs your contact email in the A2_CONTACT_EMAIL environment variable. Makes six
small requests in total, to keep traffic low as the providers ask.

    python scripts/save_samples.py
"""

import json
from pathlib import Path

import requests

from a2.weather.config import contact_email, user_agent
from a2.weather.forecast import FORECAST_URL, DAILY_VARIABLES
from a2.weather.geocoding import GEOCODING_URL
from a2.weather.metno import METNO_URL

OUT = Path(__file__).resolve().parents[1] / "tests" / "data"


def save(name: str, url: str, params: dict, headers: dict) -> None:
    response = requests.get(url, params=params, headers=headers, timeout=20)
    payload = {"status": response.status_code, "content_type": response.headers.get("Content-Type", ""),
               "body": response.json()}
    (OUT / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{name:<22} HTTP {response.status_code}  {response.headers.get('Content-Type', '')}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": user_agent(contact_email())}
    geo = {"count": 10, "language": "en", "format": "json"}
    save("geocode_dresden", GEOCODING_URL, {"name": "Dresden", **geo}, headers)
    save("geocode_springfield", GEOCODING_URL, {"name": "Springfield", **geo}, headers)
    save("geocode_no_results", GEOCODING_URL, {"name": "Qzxqzxqzx", **geo}, headers)
    lat, lon = 51.0509, 13.7383                                    # Dresden
    daily = {"latitude": lat, "longitude": lon, "daily": ",".join(DAILY_VARIABLES),
             "timezone": "auto", "forecast_days": 7}
    save("forecast_dresden", FORECAST_URL, daily, headers)
    save("forecast_invalid_latitude", FORECAST_URL, {**daily, "latitude": 100}, headers)
    save("metno_dresden", METNO_URL, {"lat": lat, "lon": lon}, headers)
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
