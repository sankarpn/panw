from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherForecastSpec:
    """Everything API-specific about the Open-Meteo forecast endpoint.

    The path and request params live here, not in the test body. Value-correctness
    bounds (e.g. plausible temperature range) live with the validator — see
    src/validators/weather.py.
    """

    path: str = "/forecast"
    hourly_variable: str = "temperature_2m"

    def params_for(self, city):
        return {
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "hourly": self.hourly_variable,
            "timezone": "auto",
        }


@dataclass(frozen=True)
class CurrentWeatherSpec:
    """Open-Meteo current-weather endpoint binding (same /forecast path, current=).

    Value-correctness bounds live with the validator — see src/validators/weather.py.
    """

    path: str = "/forecast"
    current_variable: str = "temperature_2m"

    def params_for(self, latitude, longitude):
        return {
            "latitude": latitude,
            "longitude": longitude,
            "current": self.current_variable,
            "timezone": "auto",
        }
