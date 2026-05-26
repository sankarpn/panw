import json
from pathlib import Path

import allure
import pytest

from src.descriptors import COUNTRIES
from src.lookups import common_name, region_of
from src.validators import CountryValidator

pytestmark = pytest.mark.countries  # this whole module targets the countries env

CASES = json.loads(
    (Path(__file__).parent.parent / "test_data" / "countries.json").read_text()
)
# A tiny sample of country names used ONLY to smoke-test the literal /name SEARCH
# endpoint in test_country_appears_in_its_region. Full membership coverage does NOT
# depend on this file — test_every_country_appears_in_its_region derives the whole
# universe from /all. Deliberately no region mapping: the region is read from each
# /name response, so the check is endpoint agreement, not real-world geography.
NAME_SEARCH_SAMPLE = json.loads(
    (Path(__file__).parent.parent / "test_data" / "name_search_sample.json").read_text()
)


@allure.feature("countries")
def test_europe_region_count(environment):
    spec = COUNTRIES.endpoint("europe_region")
    countries = environment.client.get(spec.path).json()
    count = len(countries)
    assert count >= environment.min_results_count, (
        f"/region/europe returned {count}, below the env floor of "
        f"{environment.min_results_count}"
    )
    assert count >= spec.expected_min, (
        f"/region/europe returned {count}, below the endpoint expectation of "
        f"{spec.expected_min}"
    )


@allure.feature("countries")
@pytest.mark.parametrize("case", CASES, ids=[c["search_term"] for c in CASES])
def test_country_by_name(environment, case):
    response = environment.client.get(
        COUNTRIES.name_lookup(case["search_term"]),
        expect_status=case["expected_status"],
    )
    if case["expected_status"] != 200:
        return  # negative path verified by the status check; nothing more to validate
    CountryValidator.validate(response.json()[0])


@allure.feature("countries")
def test_all_have_population(environment):
    spec = COUNTRIES.endpoint("all_population")
    countries = environment.client.get(spec.path, params=COUNTRIES.all_params()).json()
    assert len(countries) >= environment.min_results_count, "no countries returned"
    for country in countries:
        if common_name(country) in COUNTRIES.uninhabited_territories:
            continue  # documented uninhabited territory; legitimately reports 0
        population = country["population"]
        assert population > 0, (
            f"{common_name(country)}: population {population} is not > 0"
        )


@allure.feature("countries")
@pytest.mark.parametrize("name", NAME_SEARCH_SAMPLE, ids=NAME_SEARCH_SAMPLE)
def test_country_appears_in_its_region(environment, name):
    """A country found via the /name SEARCH endpoint must appear in /region results.

    This is the SAMPLED smoke test for the literal /name endpoint — it exercises the
    search path for a few countries. Exhaustive coverage of "every country appears in
    its region" lives in test_every_country_appears_in_its_region (driven by /all).

    SCOPE — read before changing the assertion. This is a CONSISTENCY check that two
    endpoints of the SAME API agree with each other. It is deliberately NOT a factual,
    real-world geography check:

      * We never assert a country *truly* belongs to a region.
      * We read whatever region /name reports for the country, then assert that
        /region/<that region> lists it too.
      * If the API claimed Germany's region was "Asia" and /region/asia returned
        Germany, this test would PASS on purpose — the two views are internally
        consistent. Real-world correctness of the region label is out of scope and
        is intentionally not tested here.
    """
    country = environment.client.get(COUNTRIES.name_lookup(name)).json()[0]

    # Region comes from the API's OWN /name response, never a hardcoded expectation
    # — that is what keeps this a cross-endpoint agreement check rather than a check
    # against real-world ground truth.
    region = region_of(country)

    members = environment.client.get(COUNTRIES.region_lookup(region)).json()
    assert common_name(country) in {common_name(c) for c in members}, (
        f"consistency failure: /name puts {common_name(country)} in region "
        f"{region!r}, but /region/{region} does not list it"
    )


@allure.feature("countries")
def test_every_country_appears_in_its_region(environment):
    """Exhaustive /all -> /region cross-reference, enumerated from the full /all catalog.

    Enumerates the FULL catalog via /all and asserts every country appears in the
    /region listing for the region it reports — no curated data file, ~7 requests.
    Same SCOPE as test_country_appears_in_its_region: a consistency check that two
    endpoints (/all <-> /region) agree, NOT a real-world geography check. The region
    is read from each country's own record, never an external expectation. A country
    whose reported region has no matching /region listing (e.g. a brand-new region)
    is flagged too.
    """
    catalog = environment.client.get(
        COUNTRIES.all_path, params=COUNTRIES.region_params()
    ).json()
    assert len(catalog) >= environment.min_results_count, "empty country catalog"

    # Build region -> {common names} from the by-region view, once per region.
    listings = {
        region: {
            common_name(c)
            for c in environment.client.get(
                COUNTRIES.region_lookup(region), params=COUNTRIES.region_params()
            ).json()
        }
        for region in COUNTRIES.regions
    }

    missing = [
        common_name(country)
        for country in catalog
        if common_name(country) not in listings.get(region_of(country), set())
    ]
    assert not missing, (
        f"{len(missing)} country(ies) absent from their reported region's /region "
        f"listing (first 10): {missing[:10]}"
    )


@allure.feature("countries")
@pytest.mark.parametrize("region", COUNTRIES.regions, ids=[r.lower() for r in COUNTRIES.regions])
def test_region_listing_is_consistent(environment, region):
    # Exhaustive cross-check: every country a /region listing returns must report
    # that same region. Covers all countries across all regions, one request each.
    members = environment.client.get(
        COUNTRIES.region_lookup(region), params=COUNTRIES.region_params()
    ).json()
    assert len(members) >= environment.min_results_count, f"no countries in {region}"
    for country in members:
        assert region_of(country) == region, (
            f"{common_name(country)} appears in /region/{region} but reports "
            f"region {region_of(country)!r}"
        )
