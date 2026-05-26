import json
from pathlib import Path

import allure
import pytest

from src.descriptors import WeatherForecastSpec
from src.validators import WeatherValidator
from src.validators.base import assert_in_range, assert_min_count

pytestmark = pytest.mark.weather

CITIES = json.loads(
    (Path(__file__).parent.parent / "test_data" / "cities.json").read_text()
)
FORECAST = WeatherForecastSpec()


@allure.feature("weather")
@pytest.mark.parametrize("city", CITIES, ids=[c["name"] for c in CITIES])
def test_forecast(environment, city):
    # SLA + 200 status are enforced inside environment.client.get.
    response = environment.client.get(FORECAST.path, params=FORECAST.params_for(city))

    # Typed validator checks timezone present (str) + hourly present (dict).
    data = WeatherValidator.validate(response.json())

    assert_min_count(
        data.hourly_temps,
        threshold=environment.min_results_count,
        label=f"{city['name']} hourly entries",
    )
    for temp in data.hourly_temps:
        assert_in_range(
            temp,
            FORECAST.temp_min_celsius,
            FORECAST.temp_max_celsius,
            label=f"{city['name']} temp",
        )
