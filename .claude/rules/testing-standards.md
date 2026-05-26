# Testing Standards

Test-authoring conventions for this framework. These govern *how a test is
written*, complementing `framework-rules.md` (which governs the architecture).
Like the framework rules, every standard here is specific to this project and
checkable against the repo.

---

## 1. Weather data is always parametrized from a committed JSON

- Weather inputs come from a committed JSON under `test_data/`, loaded and passed
  to `@pytest.mark.parametrize` — never inlined in a test. The forecast test uses
  `cities.json`; the current-weather test uses `weather_current.json` (whose rows
  also carry an `expected_status` for its positive + negative cases).
- Use one file per endpoint when the rows differ — only the current-weather rows
  need `expected_status`, and a malformed-coords row must not leak into the
  forecast test's `cities.json`.
- Adding or changing a case means editing the JSON, not the test code.
- Rationale: the data is the input to the test, not part of it. Inlining couples
  test logic to a specific dataset and defeats data-driven testing.

```python
# WRONG — coordinates inlined
@pytest.mark.parametrize("lat,lon", [(52.52, 13.40), (35.68, 139.69)])
def test_forecast(environment, lat, lon): ...

# RIGHT — cities loaded from the committed JSON
CITIES = load_cities("test_data/cities.json")
@pytest.mark.parametrize("city", CITIES, ids=lambda c: c["name"])
def test_forecast(environment, city): ...
```

## 2. Every endpoint that returns a schema gets a typed validator test

- If an endpoint returns structured data, there is a test that validates it
  through its typed validator (`CountryValidator`, `WeatherValidator`).
- A test that fetches a schema-bearing response and only checks the status code
  is incomplete.
- Rationale: schema conformance is the core invariant; status-only tests give
  false confidence.

## 3. Response-time is never asserted in a test

- No test contains a timing assertion. The client enforces the SLA on every
  `.get()` (see framework-rules #1). A test with a timing check is by
  definition wrong.

## 4. The cross-reference pattern is the canonical shape for consistency checks

- A consistency test fetches from two endpoints and asserts a membership/
  relationship between the results. The `/name/germany` ∈ `/region/europe`
  test is the reference implementation.
- Any future cross-API or cross-endpoint consistency test follows this shape:
  fetch A, fetch B, extract comparable keys via a shared helper, assert relation.
- Rationale: documenting one canonical shape keeps consistency tests uniform
  and prevents each one from inventing its own structure.

## 5. Markers are registered and applied per environment

- Each test **module** declares its environment via a module-level
  `pytestmark = pytest.mark.<env>` (e.g. `pytest.mark.countries`); the module-scoped
  `environment` fixture resolves it. These markers are registered **dynamically** in
  the root `conftest.py` (`pytest_configure`), one per environment name in
  `environments.yaml` — so there are no unregistered-marker warnings, it works
  under `--strict-markers`, and adding an environment needs no `pytest.ini` edit.
- The env marker drives selective runs (`--env` / `-m`); the per-test
  `@allure.feature` label drives the per-environment Allure sections.
- Rationale: the `--env` flag and the per-environment report sections both
  rely on tests being attributable to an environment.

## 6. Assertions carry a message; failures must be diagnosable

- Every assertion includes a message that names what was expected and what was
  seen (e.g. `f"{city['name']}: temp {t}°C outside [-80, 60]"`).
- A bare `assert x` with no message is not acceptable for a value/range check.
- Rationale: a CI failure should be readable from the job log without
  re-running locally — this matters for the pipeline's job-output summary.

## 7. Positive and negative coverage where the endpoint allows it

- Where an endpoint can return a meaningful negative (e.g. a nonsense country
  name → empty/404), include a test for that path, not only the happy path.
- **Negative cases are carried as data, not special-cased in code.** Each test
  data row carries an `expected_status` field; positive (200) and negative
  (404) rows flow through the SAME parametrized test. The test asserts the
  response matches `expected_status`, then runs schema/value checks only on the
  positive path.

```json
// test data row carries its own expectation
[
  {"search_term": "germany", "expected_status": 200},
  {"search_term": "not_a_real_country_xyz", "expected_status": 404}
]
```
```python
def test_country(environment, case):
    resp = environment.client.get(spec.path(case["search_term"]),
                                  expect_status=case["expected_status"])
    if case["expected_status"] != 200:
        return  # negative path verified by the status check; nothing more to validate
    CountryValidator.validate(resp.json()[0])
```
> **Coupling note (decide at client design):** this pattern requires the client
> to NOT blindly raise on non-2xx. Either the client takes `expect_status` and
> raises only on a MISMATCH, or it never auto-raises and the test inspects the
> status. If `get()` calls `raise_for_status()` unconditionally, a 404 row
> throws before you can assert it and negative tests can't run. See
> framework-rules (client section).

- Do not invent negative cases the API can't actually produce (see the
  edge-case discipline below).

## 8. Edge cases must be real for THESE APIs

- Both target APIs are free, no-auth, and the endpoints used are unpaginated.
- Do NOT write tests for auth-token expiry, rate-limit/429 handling, or
  pagination — they don't apply here. (This is a known hallucination class;
  see CLAUDE_LOG.)
- DO cover: empty result sets, missing optional fields, absent timezone,
  out-of-range values, malformed coordinates.
- Rationale: a test for a condition the API can't produce is dead weight and
  signals the author didn't understand the target.
