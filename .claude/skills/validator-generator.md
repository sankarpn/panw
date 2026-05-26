# Skill: validator-generator

**Purpose:** Given a sample JSON response, generate a **typed pydantic validator**
for that contract — one `BaseModel` per API contract.

This skill prevents the most likely drift: collapsing validation into one generic,
schema-interpreting mega-validator. Do NOT do that. (framework-rules #4)

---

## Input
- A sample JSON response (actual payload or representative excerpt).
- The contract name (e.g. `Country`, `Weather`).
- Which top-level fields are REQUIRED vs optional.

## Output
A `BaseModel` in `src/validators/<contract>.py` whose **fields are the schema**,
with a `validate(raw)` classmethod that delegates to `model_validate` and returns
an instance. Export it from `src/validators/__init__.py`.

## Hard constraints (do not violate)
- One `BaseModel` per contract. NEVER a generic validator that maps type-name
  strings to types at runtime (no `TYPE_MAP`). The model IS the contract.
- Use **strict mode**: `model_config = ConfigDict(strict=True)` — no coercion, so
  a string where an int is expected fails (same guarantee as the old `isinstance`
  checks). Extra fields in the response are ignored by default.
- Field types are real Python types. Use BARE containers (`dict`, `list`) when you
  only need "is a dict / is a list"; use nested `BaseModel`s when you want to check
  structure (e.g. `name.common: str`).
- Genuinely optional fields (a key the API omits for some records, e.g. `borders`
  for borderless countries, `capital` for Antarctica) are typed `X | None = None`.
  pydantic handles both the absent-key and present-null cases.
- The validator imports NOTHING from `tests/` and NOTHING reporting-related
  (no allure). (framework-rules #5, code-style #5)
- Value/range checks stay OUT of the validator — tests call `assert_in_range` /
  `assert_min_count` from `src/validators/base.py` (one concern per helper —
  code-style #6). If a test needs a nested series, expose it via `@property`
  (e.g. `WeatherValidator.hourly_temps` reads `hourly["temperature_2m"]`).

## Template
```python
from pydantic import BaseModel, ConfigDict


class CountryValidator(BaseModel):
    """Fields ARE the schema; strict mode = no coercion."""

    model_config = ConfigDict(strict=True)

    # required (assignment-specified for /name/germany)
    name: dict
    capital: list
    population: int
    currencies: dict
    languages: dict
    # optional example — omitted by the API for some records, so it may be absent
    borders: list | None = None

    @classmethod
    def validate(cls, raw: dict) -> "CountryValidator":
        return cls.model_validate(raw)  # raises pydantic.ValidationError on mismatch
```
> Want stronger checks than "is a dict"? Replace `name: dict` with a nested model:
> `class _Name(BaseModel): common: str` then `name: _Name`. Now `name.common` must
> be a str, not just "name is some dict".

## Generation steps
1. Inspect the sample JSON; list top-level fields and their Python types.
2. Mark required vs optional per the assignment (optional -> `X | None = None`).
3. Emit the `BaseModel` with `ConfigDict(strict=True)`; `validate()` returns
   `cls.model_validate(raw)`.
4. Expose derived/nested data the test needs via `@property`.
5. Place in `src/validators/<contract>.py`, export from `src/validators/__init__.py`,
   and add a test that calls `<Contract>Validator.validate(...)`. (testing-standards #2)

## Good vs the drift to avoid
- GOOD: `CountryValidator` and `WeatherValidator` — two small strict `BaseModel`s,
  each `cls.model_validate(raw)`, with shared count/range helpers in `base.py`.
- DRIFT (reject): a single `SchemaValidator(schema={"name": "dict", ...})` mapping
  type-name strings at runtime. If you write a `TYPE_MAP`, stop — that's a DSL, not
  a contract.
