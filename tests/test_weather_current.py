# Generated with the test-generator skill (.claude/skills/test-generator.md) for the
# Open-Meteo current-weather endpoint; CurrentWeatherValidator + the CurrentWeatherSpec
# descriptor were produced by the validator-generator skill. Reviewed, kept, and
# verified live. See CLAUDE_LOG.md ("Skills, exercised").
import json
from pathlib import Path

import allure
import pytest

from src.descriptors import CurrentWeatherSpec
from src.validators import CurrentWeatherValidator
from src.validators.base import assert_in_range

pytestmark = pytest.mark.weather

CURRENT = CurrentWeatherSpec()
CASES = json.loads(
    (Path(__file__).parent.parent / "test_data" / "weather_current.json").read_text()
)


@allure.feature("weather")
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_current_weather(environment, case):
    # SLA + status are enforced inside environment.client.get.
    response = environment.client.get(
        CURRENT.path,
        params=CURRENT.params_for(case["latitude"], case["longitude"]),
        expect_status=case["expected_status"],
    )
    if case["expected_status"] != 200:
        return  # negative path verified by the status check; nothing more to validate

    data = CurrentWeatherValidator.validate(response.json())
    assert_in_range(
        data.current_temp,
        CURRENT.temp_min_celsius,
        CURRENT.temp_max_celsius,
        label=f"{case['name']} current temp",
    )
