# Skill: test-generator

**Purpose:** Given an endpoint path + HTTP method + the response fields to check,
generate a complete pytest test for THIS framework — using the `environment`
fixture, the endpoint descriptor, the typed validator, the shared assertion helpers,
the correct env marker, and the matching `@allure.feature(...)`.

Not generic pytest scaffolding; it produces tests that fit the shared-client /
typed-validator architecture.

---

## Input
- Endpoint path (relative to base_url) — referenced via the DESCRIPTOR, never a literal.
- HTTP method (GET for this assignment).
- Response fields / what to validate.
- Environment (`countries` | `weather`) — drives both the marker and the allure feature.
- Data-driven (parametrized from committed JSON) or single.

## Output
A `tests/test_<area>.py` file (or added function) that:
- fetches via `environment.client` (SLA + status enforced there),
- declares its env via a module-level `pytestmark = pytest.mark.<env>` (the
  module-scoped `environment` fixture resolves it) and carries `@allure.feature("<env>")` per test,
- resolves path/params/expectations from the descriptor,
- delegates schema checks to the typed validator,
- delegates count/range checks to helpers in `src/validators/base.py`,
- carries diagnostic assertion messages,
- includes negatives ONLY as data rows through the same parametrized test.

## Hard constraints (do not violate)
- NO timing assertion — the client enforces the SLA. (framework-rules #1)
- NO bare threshold literals. Env-wide floor = `environment.min_results_count`;
  endpoint-binding expectations (e.g. `spec.expected_min` on a region) live on the
  descriptor; value-correctness bounds (e.g. plausible temperature range) live with
  the validator (e.g. `TEMP_MIN_C` / `TEMP_MAX_C` in `src/validators/weather.py`).
  Never `40` / `-80` / `60` inline. (framework-rules #2 + #3, code-style #2)
- Read config via attribute access on `environment`, never dict keys. (code-style #3)
- Paths/params come from the descriptor, not literals in the test. (code-style #4)
- Data-driven tests parametrize from committed JSON, never inline data.
  (testing-standards #1)
- Negatives are carried as DATA (an `expected_status` row) flowing through the SAME
  parametrized test — not a separate hardcoded function. (testing-standards #7)
- Every test carries `@allure.feature("<env>")` so the report splits per environment.
- Do NOT import from other test files. (framework-rules #5)
- Only negatives the API can actually produce. No auth/rate-limit/pagination tests.
  (testing-standards #8)

## Templates

### Countries: positive + data-driven negative (one parametrized test)
`test_data/countries.json`:

    [
      {"search_term": "germany", "expected_status": 200},
      {"search_term": "not_a_real_country_xyz", "expected_status": 404}
    ]

```python
import json
from pathlib import Path

import allure
import pytest

from src.descriptors import COUNTRIES
from src.validators import CountryValidator

pytestmark = pytest.mark.countries   # module-scoped fixture resolves env from this

CASES = json.loads(
    (Path(__file__).parent.parent / "test_data" / "countries.json").read_text()
)

@allure.feature("countries")
@pytest.mark.parametrize("case", CASES, ids=[c["search_term"] for c in CASES])
def test_country_by_name(environment, case):
    resp = environment.client.get(
        COUNTRIES.name_lookup(case["search_term"]),   # path from descriptor
        expect_status=case["expected_status"],         # client raises on mismatch
    )
    if case["expected_status"] != 200:
        return  # negative verified by the status check
    CountryValidator.validate(resp.json()[0])          # typed validator
```
> Keyed endpoints with a fixed expectation use `COUNTRIES.endpoint("europe_region")`
> → returns `EndpointSpec(path, expected_min)`. Free-text lookups use
> `COUNTRIES.name_lookup(term)` / `COUNTRIES.region_lookup(region)`.

### Weather: parametrized from cities.json, typed validator + shared helpers
```python
import json
from pathlib import Path

import allure
import pytest

from src.descriptors import WeatherForecastSpec
from src.validators import WeatherValidator
from src.validators.weather import TEMP_MAX_C, TEMP_MIN_C
from src.validators.base import assert_in_range, assert_min_count

pytestmark = pytest.mark.weather   # module-scoped fixture resolves env from this

CITIES = json.loads(
    (Path(__file__).parent.parent / "test_data" / "cities.json").read_text()
)
FORECAST = WeatherForecastSpec()

@allure.feature("weather")
@pytest.mark.parametrize("city", CITIES, ids=[c["name"] for c in CITIES])
def test_forecast(environment, city):
    resp = environment.client.get(FORECAST.path, params=FORECAST.params_for(city))
    data = WeatherValidator.validate(resp.json())       # timezone + hourly schema
    assert_min_count(
        data.hourly_temps,
        threshold=environment.min_results_count,         # env-wide floor
        label=f"{city['name']} hourly entries",
    )
    for temp in data.hourly_temps:
        assert_in_range(
            temp,
            TEMP_MIN_C,                                  # value-correctness bound (validator side)
            TEMP_MAX_C,
            label=f"{city['name']} temp",
        )
```
> `cities.json` rows use keys `name`, `latitude`, `longitude`. The descriptor's
> `params_for(city)` builds the query params — the test never inlines them.

## Generation steps
1. Environment -> module-level `pytestmark = pytest.mark.<env>` (resolved by the
   module-scoped fixture) + `@allure.feature("<env>")` per test.
2. Data-driven vs single -> parametrize from JSON or not.
3. Resolve path/params/expectations from the descriptor (add an entry if missing).
4. Choose the validator (generate one via validator-generator if absent).
5. Positive path first; add negatives ONLY as `expected_status` data rows.
6. Use `assert_min_count` / `assert_in_range` from base; give every assertion a message.
