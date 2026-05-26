from dataclasses import dataclass

from src.client import ApiClient


@dataclass(frozen=True)
class Environment:
    """Typed, per-environment contract handed to tests by the fixture.

    Tests read these as attributes (environment.client, environment.min_results_count)
    — never as dict keys and never from the YAML file directly.
    """

    client: ApiClient
    min_results_count: int
    max_response_time: float
