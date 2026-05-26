from dataclasses import dataclass


@dataclass(frozen=True)
class WeatherForecastSpec:
    """Everything API-specific about the Open-Meteo forecast endpoint.

    The path and expectation values live here, not in the test body.
    """

    path: str = "/forecast"
    hourly_variable: str = "temperature_2m"
    temp_min_celsius: float = -80.0
    temp_max_celsius: float = 60.0

    def params_for(self, city):
        return {
            "latitude": city["latitude"],
            "longitude": city["longitude"],
            "hourly": self.hourly_variable,
            "timezone": "auto",
        }


@dataclass(frozen=True)
class CurrentWeatherSpec:
    """Open-Meteo current-weather endpoint binding (same /forecast path, current=)."""

    path: str = "/forecast"
    current_variable: str = "temperature_2m"
    temp_min_celsius: float = -80.0
    temp_max_celsius: float = 60.0

    def params_for(self, latitude, longitude):
        return {
            "latitude": latitude,
            "longitude": longitude,
            "current": self.current_variable,
            "timezone": "auto",
        }
