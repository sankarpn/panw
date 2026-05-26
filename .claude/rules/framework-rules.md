# Framework Rules

Architecture constraints for the multi-environment API test framework.
These are **enforceable invariants**, not style preferences — each one is
checkable against the repo. If a generated file violates one, it is wrong
regardless of whether the tests pass.

The framework runs the *same validation logic* against two unrelated APIs
(REST Countries, Open-Meteo). Everything below exists to keep that single
shared abstraction intact as APIs are added.

---

## 1. The response-time SLA lives only in `ApiClient`

- `ApiClient.get()` is the **single site** that measures and asserts response
  time against `max_response_time`. No other code times a request.
- A timing assertion (`assert elapsed < ...`, `response.elapsed`, `time.time()`
  bracketing a call) anywhere under `tests/` is a bug.
- **Status handling:** `get()` must NOT call `raise_for_status()`
  unconditionally — that would make negative tests (expected 404) impossible.
  Instead `get()` accepts `expect_status` (default 200) and raises only on a
  MISMATCH between actual and expected. This keeps positive and negative cases
  flowing through one parametrized test. (see testing-standards #7)
- Rationale: response-time is an invariant of *every* environment. Centralizing
  it in the client is what makes "both APIs respond within the YAML threshold"
  a property of the framework instead of a line copied into every test.

```python
# WRONG — timing asserted in the test, threshold hardcoded
def test_forecast(environment):
    r = environment.client.get("/forecast", params=...)
    assert r.elapsed.total_seconds() < 3.0      # SLA leaked into test + magic number

# RIGHT — the client already enforced the SLA on .get(); the test only checks data
def test_forecast(environment):
    r = environment.client.get("/forecast", params=...)
    assert WeatherValidator.validate(r.json()) is not None
```

## 2. Config enters through one door

- The **only** path for config into a test is the `environment` fixture, which
  yields an `Environment` object.
- Tests read `environment.client`, `environment.min_results_count`,
  `environment.max_response_time` — never a raw dict, never the YAML file.
- No test, validator, descriptor, or `src/` module opens
  `config/environments.yaml` directly. Only the fixture does.
- A literal threshold value (`2.0`, `3.0`, `40`, `1`) appearing anywhere under
  `src/` or `tests/` is a bug — those numbers live in YAML and nowhere else.
- Rationale: "zero hardcoded values" means values enter the system exactly once.
  One injection point is what makes that auditable.

```python
# WRONG — bare magic number floating in the test
def test_europe_count(environment):
    r = environment.client.get("/region/europe")
    assert len(r.json()) > 40                   # where did 40 come from? what does it mean?

# RIGHT — endpoint-specific expectation lives in that endpoint's descriptor;
#         env-wide floor (min_results_count) still applies underneath
def test_europe_count(environment):
    spec = COUNTRIES.endpoint("europe_region")  # spec.expected_min == 40, named + located
    r = environment.client.get(spec.path)
    count = len(r.json())
    assert count >= environment.min_results_count   # env-wide floor
    assert count >= spec.expected_min               # this endpoint's specific expectation
```

> Note the distinction this example encodes: `min_results_count` (=1) is an
> environment-wide floor that applies to *every* endpoint; `40` is a
> *this-endpoint* expectation. They are different concepts and live in
> different places — the floor in YAML, the endpoint expectation in the
> descriptor. Folding `40` into `min_results_count` to look "config-driven"
> would silently weaken the assertion.

## 3. Descriptors and validators are separate concerns and never merge

- `src/descriptors/` answers **"what endpoints does this API expose, and which
  validator checks each?"** — paths, params, bindings.
- `src/validators/` answers **"is this response well-formed?"** — schema and
  value checks.
- A file in `descriptors/` must not define schema/type checks; a file in
  `validators/` must not define endpoint paths.
- Neither imports from the other across that boundary.
- Rationale: this split is what lets a third API reuse an existing validator
  without dragging in another API's endpoint map. Collapsing them couples
  "what to call" with "how to check" and kills extensibility.

## 4. Schemas are typed code, not serialized config

- A validator is a pydantic `BaseModel` (strict mode) whose **fields are its
  schema**. `validate()` delegates to `model_validate`, which checks presence +
  type and raises `ValidationError` on a mismatch.
- Never define a schema as a dict-of-strings type spec in YAML/JSON, and never
  write a `validate()` that interprets such a spec at runtime.
- Rationale: a string-keyed type map is untyped code wearing a config costume —
  it loses type-checking, IDE navigation, and refactor-safety. A pydantic model
  is the opposite: typed code that the language and the library both check. Config
  is for *values an operator tunes*; contracts are for *code the language checks*.
  (The `validator-generator` skill generates these classes — schemas are
  code by design.)

```python
# WRONG — schema serialized into YAML, interpreted at runtime by a string DSL
#   country_schema:
#     name: dict
#     population: int
def validate(data, field_spec):
    for field, type_name in field_spec.items():
        assert isinstance(data[field], TYPE_MAP[type_name])   # untyped, no IDE, no refactor

# RIGHT — the pydantic model IS the schema; the library checks it (strict: no coercion)
from pydantic import BaseModel, ConfigDict

class CountryValidator(BaseModel):
    model_config = ConfigDict(strict=True)
    name: dict
    capital: list
    population: int
    currencies: dict
    languages: dict

    @classmethod
    def validate(cls, raw: dict) -> "CountryValidator":
        return cls.model_validate(raw)   # raises ValidationError on missing / wrong-typed field
```

## 5. Import direction is one-way

- `tests/` imports from `src/`. `src/` **never** imports from `tests/`.
- Test files **never** import from other test files
  (`test_weather.py` must not import from `test_countries.py`).
- Shared test helpers live in `src/` or `conftest.py`, never in a sibling
  test module.
- Rationale: a single cross-test import secretly couples the two suites and
  breaks the "API-agnostic, independently runnable" promise. One-way imports
  keep the dependency graph a tree.

## 6. `pytest_addoption` and the `environment` fixture live in the
   top-level `conftest.py`

- The `--env` option is registered in the **root** `conftest.py` and nowhere
  else. The `environment` fixture is defined there too.
- No nested conftest redefines `--env` or the `environment` fixture.
- Rationale: option-registration hooks must be discoverable at collection
  start; a nested conftest can cause pytest to miss or warn on the hook.

## 7. Tests are thin; the abstraction does the work

- A test function fetches via `environment.client`, hands the response to a
  shared validator or assertion helper, and asserts. It does not contain
  bespoke parsing logic that belongs in a validator.
- If two tests need the same extraction/parse step, that step moves into
  `src/`, not copied between tests.
- Rationale: logic in tests can't be reused across the two APIs; logic in
  `src/` can. The reuse the rubric rewards lives in `src/`, so that's where
  non-trivial logic belongs.

```python
# WRONG — parsing/extraction logic inlined in the test (can't be reused)
def test_cross_reference(environment):
    g = environment.client.get("/name/germany").json()[0]
    e = environment.client.get("/region/europe").json()
    names = set()
    for c in e:                                 # extraction logic stuck in the test
        names.add(c["name"]["common"])
    assert g["name"]["common"] in names

# RIGHT — extraction lives in a shared helper/validator; the test stays thin
def test_cross_reference(environment):
    g = environment.client.get("/name/germany").json()[0]
    e = environment.client.get("/region/europe").json()
    assert common_name(g) in {common_name(c) for c in e}   # common_name() lives in src/
```

## 8. Adding a new API touches only data and config

- The extensibility test for any change: **adding a third environment must
  require only (a) a new YAML block, (b) a new descriptor, (c) a new validator
  if no existing one fits — and zero edits to `ApiClient` or the assertion
  helpers.**
- If a change forces an edit to the client or the shared validation engine to
  accommodate one specific API, the abstraction has leaked — stop and fix the
  abstraction instead.
- Rationale: this is the framework's reason to exist. It's the question to ask
  of every PR.
