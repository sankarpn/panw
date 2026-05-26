# Multi-Environment API Test Framework — REST Countries + Open-Meteo

A pytest framework that runs the **same validation logic against two unrelated
APIs** treated as interchangeable "environments". All environment differences
(base URLs, thresholds) live in `config/environments.yaml`; the tests are
API-agnostic. The architecture — a shared SLA-enforcing client, a shared
validation engine, and all API-specific knowledge pushed into typed *descriptors*
and *validators* — is the point of the project.

| Environment | API | Base URL |
|---|---|---|
| `countries` | REST Countries | `https://restcountries.com/v3.1` |
| `weather` | Open-Meteo | `https://api.open-meteo.com/v1` |

---

## Architecture at a glance

```
config/environments.yaml   operator-tunable values only (base_url, thresholds)
conftest.py                --env flag + the `environment` fixture (the ONE config door)
src/
  client.py                ApiClient — pooled session, retries transient failures, enforces the SLA + status, logs each call
  environment.py           Environment dataclass (typed contract handed to tests)
  descriptors/             WHAT each API exposes: paths, params, endpoint expectations
  validators/              IS the response well-formed: strict pydantic models + shared assert helpers (base.py)
  lookups.py               shared extraction helpers (common_name, region_of)
tests/                     thin tests: fetch -> validate -> assert (marked per environment)
test_data/                committed JSON inputs (cities, country cases, name samples)
.claude/                   rules/ (architecture constraints) + skills/ (generators)
.github/workflows/ci.yml   CI: run suite, upload Allure report, fail on test/quality-gate
```

**How a test runs (the flow that makes it API-agnostic):**

```text
environments.yaml ──▶ fixture ──▶ environment {client + thresholds}
                                        │ injected
                                        ▼
  thin test (conductor):
    descriptor ─path─▶ client.get ─response─▶ validator ─data─▶ assert_* ─▶ pass/fail
    (per-API)          (SHARED)              (per-API)        (SHARED)
```

1. **Startup:** pytest loads `conftest.py` and registers `--env` + one marker per
   environment (read from the YAML).
2. **Per test:** the `environment` fixture turns that env's YAML block into a typed
   `Environment` (a ready `ApiClient` + thresholds); pytest injects it.
3. **The thin test conducts:** ask the **descriptor** for the path → call
   `environment.client` (the **shared** engine: HTTP + SLA + status) → hand the
   response to the **validator** (shape) → check values with the **shared `assert_*`
   helpers** → pass/fail.

Same path for both APIs; only the descriptor and validator differ.

Design rules the code is held to live in `.claude/rules/` (`framework-rules.md`,
`code-style.md`, `testing-standards.md`).

---

## Setup

**Prerequisites:** Python 3.10+ (developed and CI-tested on **3.14**).

```powershell
# from the repo root
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS / Linux

# Windows / behind a corporate proxy: use the dev file (adds `truststore`,
# which makes Python trust the OS certificate store for TLS):
pip install -r requirements-dev.txt

# Plain environments (CI, Linux):
pip install -r requirements.txt
```

`requirements.txt`: `pytest`, `requests`, `pyyaml`, `allure-pytest`, `pydantic`.
`requirements-dev.txt`: the above + `truststore` (TLS shim for corporate CAs).

---

## Running the tests

The tests hit the **live** public APIs (free, no auth), so you need network
access.

```powershell
python -m pytest                    # run BOTH environments (19 tests)
python -m pytest --env countries    # only the REST Countries suite
python -m pytest --env weather      # only the Open-Meteo suite
```

Other useful selectors:

```powershell
python -m pytest -m weather                       # select by marker (same effect as --env)
python -m pytest -k europe                         # run tests whose name matches "europe"
python -m pytest "tests/test_weather.py::test_forecast[Berlin]"   # one case
python -m pytest -v -ra -l                         # verbose + summary + show locals on failure
```

- **`--env`** is a custom flag (registered via `pytest_addoption` in the root
  `conftest.py`). With no flag, every test runs against the environment its
  marker declares; with a flag, tests bound to the other environment are
  **skipped** (not failed).
- The response-time **SLA is enforced inside the client** on every request —
  there is no timing assertion in any test.

### Seeing request/response logs

Logging is captured at `INFO` (`pytest.ini`) and shown automatically for
**failing** tests (the "Captured log call" section), so passing runs stay quiet.
To stream it live for any run:

```powershell
python -m pytest --log-cli-level=INFO
```

You'll see one line per request and response, e.g.:

```
INFO  src.client GET https://restcountries.com/v3.1/region/europe params=None
INFO  src.client   -> 200 in 0.611s
```

---

## Allure report (per-environment sections)

`allure-pytest` records results; the **Allure CLI** renders the HTML report.

```powershell
# 1) run and capture results
python -m pytest --alluredir=allure-results

# 2) render + open the combined report (requires the Allure CLI installed)
allure serve allure-results
#   or build a static site:
allure generate allure-results --clean -o allure-report
```

Install the Allure CLI locally with Scoop (`scoop install allure`),
Homebrew (`brew install allure`), or npm (`npm i -g allure-commandline`).
Every test carries `@allure.feature("countries"|"weather")`, so the report's
**Behaviors** tab splits cleanly into a **countries** section and a **weather**
section. (CI generates and uploads this report automatically — see below.)

---

## Continuous integration

`.github/workflows/ci.yml` runs on push to any branch and:

1. sets up Python + installs dependencies,
2. runs the full suite (both environments) with `--alluredir` + JUnit XML,
3. writes a pass/fail/skip **summary table** to the job output,
4. renders the Allure HTML report and **uploads it as the `test-report` artifact**
   (alongside the raw results and `junit.xml`),
5. **fails the pipeline** if any test fails — the quality gate. Because the
   response-time SLA is enforced in the client, an SLA breach surfaces as a
   failing test, so it gates the build too.

Download the `test-report` artifact from the workflow run to view the report.

---

## How to interpret results

**The summary line** — `.` passed, `F` failed, `s` skipped (e.g. the other
environment when you pass `--env`), `E` collection/setup error.

**A failure shows three things together** — your diagnostic assertion message,
pytest's value introspection, and the captured request/response log:

```
>       assert count >= spec.expected_min, (...)
E       AssertionError: /region/europe returned 38, below the endpoint expectation of 40
E       assert 38 >= 40
------------------------------ Captured log call -------------------------------
INFO  src.client GET https://restcountries.com/v3.1/region/europe params=None
INFO  src.client   -> 200 in 0.84s
```

**Custom exceptions** make client-level failures self-explanatory:
- `SLAViolation` — a response exceeded `max_response_time` (includes URL + elapsed).
- `StatusMismatch` — actual status code didn't match the expected one (includes both).

**Skips are expected** when you filter with `--env`; they mean "this test belongs
to the other environment", not a problem.

---

## Assumptions & design decisions

- **One config door.** YAML is read only by the `environment` fixture, which
  yields a typed `Environment`. Tests use attribute access
  (`environment.client`, `environment.min_results_count`) — never dict keys,
  never the YAML file directly.
- **`base_url` is injected into the client, not exposed as a test-visible
  attribute.** The fixture reads `base_url` from YAML and builds the `ApiClient`
  with it, so each test's `environment.client` targets the right API. Tests never
  handle a raw URL — they call `environment.client.get(<descriptor path>)`. This
  keeps URL assembly in the client/descriptor layer and out of test bodies, while
  still satisfying "the fixture injects base_url" (YAML → fixture → client).
- **Thresholds vs endpoint expectations are different things.**
  `max_response_time` and `min_results_count` are environment-wide and live in
  YAML. Endpoint-specific expectations (Europe's count floor, the temperature
  range) are **descriptor attributes**, not YAML and not bare literals. The
  Europe count is encoded as `expected_min = 40` and asserted as a floor
  (`count >= 40`); REST Countries returns ~50 European countries, comfortably
  above it.
- **Descriptors vs validators never merge.** Descriptors answer "what to call";
  validators answer "is the response well-formed". Validators never import
  descriptors.
- **Validators are strict pydantic models; their fields are the schema.** Each
  contract is a `BaseModel` with `ConfigDict(strict=True)` (no type coercion);
  `validate()` calls `model_validate` and raises `ValidationError` on a missing or
  wrong-typed field. Shared count/range checks live in `src/validators/base.py`.
  Genuinely optional fields (e.g. `borders`, which the API omits for borderless
  countries) are typed `list | None`.
- **Negatives are carried as data.** A 404 case is a row in
  `test_data/countries.json` with `expected_status`, flowing through the *same*
  parametrized test as the 200 case. The client takes `expect_status` and raises
  only on a mismatch, so positive and negative paths share one test.
- **Weather data is data-driven.** The five cities come from
  `test_data/cities.json`; changing the test set means editing JSON, not code.
- **REST Countries data quirk.** `/all` includes five uninhabited territories
  that legitimately report `population: 0` (Bouvet Island, etc.). The population
  test exempts them via an allowlist in the countries descriptor — a deliberate,
  documented deviation from a strict "every country > 0".
- **No inapplicable edge cases.** Both APIs are free, no-auth, and unpaginated,
  so there are intentionally **no** tests for auth-token expiry, 401/403,
  429 rate-limiting, or pagination (see `CLAUDE_LOG.md` for the valid-vs-
  hallucinated edge-case analysis).
- **TLS on Windows.** Public-API TLS verification can fail behind a corporate
  root CA; `conftest.py` optionally injects `truststore` (a dev dependency) to
  trust the OS certificate store. It is a no-op when absent (e.g. on CI).

---

## Extending to a third API

By design this needs only: **(a)** a new block in `config/environments.yaml`,
**(b)** a new descriptor in `src/descriptors/`, and **(c)** a new validator in
`src/validators/` if no existing one fits — with **no edits** to `ApiClient` or
the shared assertion helpers. The `test-generator` and `validator-generator`
skills in `.claude/skills/` scaffold conforming tests and validators.

That works because the framework splits into a fixed **shared core** and small
**per-API plug-ins** — adding an API touches only the right column:

| Shared core (write once, reused) | Per-API plug-in (added per environment) |
|---|---|
| pytest runner; `conftest` fixture + hooks | a YAML block in `environments.yaml` |
| `ApiClient` (HTTP + SLA + status + retries) | a **descriptor** (what to call) |
| `base.py` assert helpers; `Environment` | a **validator** (right shape) — if needed |
|  | a **test file** + its JSON data |
