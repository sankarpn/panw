# Code Style

Style rules **specific to this framework**. Generic Python hygiene (PEP 8,
type hints, docstrings) is assumed and not restated here — these are the rules
that only make sense given *this* architecture. If a rule below would apply
unchanged to an unrelated Python project, it doesn't belong in this file.

---

## 1. Validators are typed models; their fields ARE the schema

- A validator is a pydantic `BaseModel` in **strict mode**
  (`model_config = ConfigDict(strict=True)`). Its annotated fields define the
  expected schema; the `validate()` classmethod delegates to `model_validate`,
  which raises `ValidationError` on a missing field or wrong type (strict mode =
  no coercion, the same guarantee the old `isinstance` checks gave).
- Never write a `validate()` that takes a dict-of-strings type spec and maps
  strings to types at runtime (a `TYPE_MAP` DSL). The model IS the contract.
  (see framework-rules #4)
- New validators live in `src/validators/`, one class per API contract. Shared
  value-level checks (`assert_min_count`, `assert_in_range`) live in
  `src/validators/base.py`.

## 2. Thresholds are never literals in `src/` or `tests/`

- Numbers like `2.0`, `3.0`, `1` enter only through the `environment` fixture,
  sourced from YAML. A literal threshold anywhere under `src/` or `tests/` is
  a bug.
- Endpoint-specific expectations (e.g. Europe's "≥40") are named constants or
  descriptor attributes, NOT bare literals and NOT folded into
  `min_results_count`.

## 3. Tests read config via attribute access, never dict keys

- `environment.client`, `environment.min_results_count` — typed attributes on
  the `Environment` dataclass.
- Never `environment["min_results_count"]` or `config["countries"]["base_url"]`
  inside a test.
- Scope: this rule governs the typed `Environment`/config contract only. Plain
  data dicts loaded from `test_data/*.json` and passed via `@pytest.mark.parametrize`
  (e.g. `case["latitude"]`, `city["name"]`) are *data, not config* — keying them is
  correct and expected, not a violation.
- Rationale: the `Environment` object is a typed contract; string-keying it
  throws away the typing it exists to provide. A JSON data row has no such typed
  contract, so attribute access wouldn't even apply.

## 4. Endpoint paths live in descriptors, not test bodies

- A test references an endpoint via its descriptor, not a string literal
  scattered in the test:
  `spec = COUNTRIES.endpoint("germany")` then `environment.client.get(spec.path)`.
- Rationale: paths are API bindings; they belong in the binding layer
  (descriptors) so a path change is one edit, not a grep-and-replace.

## 5. Allure decorators are applied at the test boundary, not buried in `src/`

- `@allure.feature`, `@allure.story`, `allure.step` go on test functions /
  inside test flow. The shared client and validators stay reporting-agnostic —
  they do not import allure.
- Rationale: keeping `src/` free of reporting concerns is what lets the same
  client/validators run under any reporter (or none). Coupling them to allure
  would break that.

## 6. One assertion concern per helper

- `assert_min_count`, `assert_in_range`, validator `.validate()` each check one
  thing and raise with a diagnostic message. Don't bundle unrelated checks into
  a single helper.
- Rationale: composable single-purpose checks are what let the two APIs reuse
  the same assertion vocabulary.

## 7. The client returns the raw response; interpretation happens above it

- `ApiClient.get()` returns the `requests.Response` (after enforcing the SLA).
  It does not `.json()`-parse, validate, or interpret payloads.
- Parsing/extraction lives in validators or shared helpers in `src/`, never in
  the client and never inlined in a test. (see framework-rules #7)
- Rationale: a client that interprets payloads stops being API-agnostic.

## 8. Naming reflects the layer

- `*Validator` for validators, `*Descriptor`/`*Spec` for descriptors,
  `test_*` for tests, `assert_*` for assertion helpers.
- A reader should infer a symbol's layer from its name without opening the file.
