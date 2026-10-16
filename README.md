# OOP with Python – Assignment 2 (Advent 2026)

**Author:** Wesonga John Collins · MSDS, OOP with Python

> Note: the brief's title reads "Assignment 2", while its page headers say "Assignment 1, Advent 2026".
> This repository answers the Assignment 2 brief: weather forecasting with web APIs and a Uganda tax engine.

| # | Mini-project | Notebook | Code |
|---|---|---|---|
| 1 | Fetching and displaying a weather forecast with Python web APIs | `notebooks/project1_weather.ipynb` | `src/a2/weather/` |
| 2 | Uganda tax engine | `notebooks/project2_tax_engine.ipynb` | `src/a2/tax/` |

## Repository layout

```
src/a2/weather/   config, errors, robust HTTP wrapper, geocoding, Open-Meteo forecast, MET Norway, cache
src/a2/tax/       Money, errors, dated PAYE schedules, Tax base + context, payroll (PAYE/NSSF/LST), VAT, CIT, planner
tests/            pytest tests (95), incl. hypothesis property tests; tests/data/ holds saved real API responses
scripts/          save_samples.py (captures the sample JSON used by the offline tests)
notebooks/        one executed notebook per mini-project
```

## Setup (Windows Command Prompt; tested with Python 3.14.8)

```
git clone https://github.com/johncollins12/oop-python-assignment-2.git
cd oop-python-assignment-2
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements.txt` pins the libraries and installs the `a2` package in editable mode (`-e .`).

## Running

```
pytest -q                                   # all tests, offline
```

**Mini-project 1 needs your contact email.** The APIs' terms require an identifying User-Agent, and the brief forbids
hardcoding contact details, so the email is read from an environment variable. Set it in the same window before
starting Jupyter (it lasts only for that window):

```
set A2_CONTACT_EMAIL=your.name@university.ac.ug
jupyter nbconvert --to notebook --execute --inplace notebooks\project1_weather.ipynb
```

Without it, the code refuses to send any request (`ConfigurationError`) rather than invent contact details.
Mini-project 1 needs internet access; its tests do not (they use the saved JSON in `tests/data/`).
Mini-project 2 runs fully offline:

```
jupyter nbconvert --to notebook --execute --inplace notebooks\project2_tax_engine.ipynb
```

`nbconvert --execute` runs a notebook top to bottom in a fresh kernel, equivalent to *Restart & Run All*.

## Libraries beyond the brief's allowed list

| Library | Why |
|---|---|
| `hypothesis` | required by Mini-project 2 for property-based tests |
| `pytest` | runs the tests (not used inside the notebooks) |
| `numpy` | listed in the brief's reproducibility rule (`np.random.default_rng`); installed with pandas |
| standard library: `dataclasses`, `typing`, `re`, `pathlib`, `hashlib`, `email.utils`, `decimal` | records and type hints, email validation, the cache extension, and exact money arithmetic |

## Data sources and rate versions

* **Open-Meteo** Geocoding and Forecast APIs — *Weather data by Open-Meteo.com* (CC BY 4.0); free tier non-commercial only.
* **MET Norway** Locationforecast 2.0 — CC BY 4.0; identifying User-Agent and caching required by its terms.
* **URA** — resident PAYE from 1 July 2026 per the notice on the Income Tax (Amendment) Act, 2026 (published
  7 September 2026); FY 2025/26 resident and non-resident PAYE per URA's PAYE rates page; VAT per URA's VAT guidance.
  Full table with links in the Mini-project 2 notebook.

## Summary of findings

**Mini-project 1 (weather).** The program geocodes a name, lets the configuration choose among candidates
("Kampala" matched five places in four countries; "Springfield" five US cities), retrieves a 7-day forecast with
local dates, and shows it as a summary, table and chart. A single request wrapper handles timeouts, HTTP errors and
retries with capped exponential back-off; the demonstrations show an invalid city, an invalid latitude (refused
locally, and HTTP 400 from the server without retry), a simulated network failure and a real timeout. Open-Meteo and
MET Norway agreed closely on temperature for Kampala but differed by a factor of two or more on some days' rainfall.
A small cache (extension) cut a repeated request from about 0.8 s to 15 ms. The report covers data flow, licensing
(Open-Meteo's free tier is non-commercial), reliability and privacy.

**Mini-project 2 (tax).** The brief's PAYE baseline is the resident schedule introduced by the Income Tax
(Amendment) Act, 2026 (effective 1 July 2026); the engine holds it alongside the FY 2025/26 and non-resident
schedules and chooses by pay date. Money is exact `Decimal` and floats are refused. Tests cover every band edge,
URA's own worked examples (PAYE 52,000 → 38,250 on UGX 500,000; VAT 90 payable) and hypothesis properties
(non-negative, monotonic, never above income). The 2026 change saves every resident above UGX 335,000 between
UGX 10,000 and 13,750 a month. In the TaxPlanner extension, paying an owner by salary beats a dividend up to about
UGX 12 million of monthly profit; above that, the flat 40.5 % dividend burden is lower than salary's marginal burden.

## AI-use declaration

I used AI tools to support the development of this assignment. The AI assistant provided assistance with interpreting the assignment requirements, exploring software design approaches and debugging Python code.
