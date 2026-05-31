CLAUDE.md
Project context for Claude Code. Read this before generating or editing any code.
What this project is
A pytest-based API test framework that runs the same validation logic
against two unrelated APIs ("environments"): REST Countries and Open-Meteo.
All environment differences (base URLs, thresholds) live in
config/environments.yaml. Tests are API-agnostic. The architecture — a
shared, SLA-enforcing client plus a shared validation engine, with all
API-specific knowledge pushed into typed descriptors and validators — is the
point of the project, not an implementation detail.

Functional Requirements (WHAT to build)

This is the what. The how/constraints are in .claude/rules/. Where this
section states a requirement (e.g. "count > 40"), the rules decide WHERE that
value lives (e.g. in the endpoint descriptor, not YAML). Don't hardcode
requirement values into test bodies — follow the rules.

Targets (both free, no auth):

REST Countries — base URL https://restcountries.com/v3.1
Open-Meteo — base URL https://api.open-meteo.com/v1
(NOTE: base URL ends at /v1. /forecast is an ENDPOINT PATH supplied by the
weather descriptor — it is NOT part of the base URL.)

config/environments.yaml — two environments, operator-tunable values only:

countries: base_url https://restcountries.com/v3.1, max_response_time 2.0, min_results_count 1
weather: base_url https://api.open-meteo.com/v1, max_response_time 3.0, min_results_count 1

Environment fixture: reads the YAML, injects base_url + thresholds based on a
--env CLI flag (via pytest_addoption). Supports --env countries,
--env weather, or no flag (runs both). Lives in the top-level (root) conftest.
Countries tests (paths are descriptor-owned, not literals in tests):

GET /region/europe — result count > 40 (the 40 is an endpoint expectation in
the descriptor; min_results_count=1 is the separate env-wide floor)
GET /name/germany — validate schema: name, capital, population, currencies, languages all present
GET /all?fields=name,population — every country has population > 0
Cross-reference: a country found via /name search must also appear in /region results

Weather tests: parametrize 5 cities from test_data/cities.json, call the
forecast endpoint per city, validate temperature in [-80, 60]°C, hourly entry
count > 0, timezone field present.
Both APIs must respond within max_response_time from YAML — enforced in the
client, never hardcoded in test code.
Reporting: combined Allure report with a separate section per environment.
