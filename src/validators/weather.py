from pydantic import BaseModel, ConfigDict

# Response contract key holding the hourly temperature series. The validator knows
# this as a contract fact; the descriptor names the same variable on the REQUEST
# side (validators never import descriptors — framework-rules #3).
HOURLY_TEMP_KEY = "temperature_2m"


class WeatherValidator(BaseModel):
    """Schema for an Open-Meteo forecast response — the fields ARE the schema.

    Strict pydantic model: timezone must be a str and hourly a dict, no coercion.
    The hourly temperature series is exposed via hourly_temps for range/count checks.
    """

    model_config = ConfigDict(strict=True)

    timezone: str
    hourly: dict

    @classmethod
    def validate(cls, raw: dict) -> "WeatherValidator":
        return cls.model_validate(raw)

    @property
    def hourly_temps(self) -> list:
        assert HOURLY_TEMP_KEY in self.hourly, (
            f"WeatherValidator: hourly missing '{HOURLY_TEMP_KEY}' "
            f"(keys={sorted(self.hourly)})"
        )
        return self.hourly[HOURLY_TEMP_KEY]


# Response contract key holding the current temperature scalar.
CURRENT_TEMP_KEY = "temperature_2m"


class CurrentWeatherValidator(BaseModel):
    """Schema for an Open-Meteo current-weather response — the fields ARE the schema.

    Strict pydantic model: timezone must be a str and current a dict, no coercion.
    The current temperature scalar is exposed via current_temp for the range check.
    """

    model_config = ConfigDict(strict=True)

    timezone: str
    current: dict

    @classmethod
    def validate(cls, raw: dict) -> "CurrentWeatherValidator":
        return cls.model_validate(raw)

    @property
    def current_temp(self) -> float:
        assert CURRENT_TEMP_KEY in self.current, (
            f"CurrentWeatherValidator: current missing '{CURRENT_TEMP_KEY}' "
            f"(keys={sorted(self.current)})"
        )
        return self.current[CURRENT_TEMP_KEY]
