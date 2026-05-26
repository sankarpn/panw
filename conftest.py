from pathlib import Path

import pytest
import yaml

from src.client import ApiClient
from src.environment import Environment

# Use the OS certificate store (e.g. Windows trust store / corporate root CAs)
# for TLS verification. No-op if truststore (a dev-only dependency) is absent.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

CONFIG_PATH = Path(__file__).parent / "config" / "environments.yaml"


def pytest_addoption(parser):
    parser.addoption(
        "--env",
        action="store",
        default=None,
        help=(
            "Run only this environment (names come from environments.yaml). "
            "Omit to run all."
        ),
    )


def _load_config():
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


def pytest_configure(config):
    """Register one marker per environment, sourced from environments.yaml.

    Adding an environment is therefore YAML-only: no pytest.ini edit and no
    unregistered-marker warning (works under --strict-markers).
    """
    for name in _load_config():
        config.addinivalue_line("markers", f"{name}: tests for the {name} environment")


@pytest.fixture(scope="module")
def environment(request):
    """Inject base_url + thresholds for the env this test MODULE is bound to.

    The module declares its env with a module-level marker
    (pytestmark = pytest.mark.countries). The fixture is module-scoped, so the
    client is built ONCE per test module and reused across its tests (then closed
    at module teardown). Valid envs are derived from environments.yaml. Honors
    --env: no flag runs every env; a flag skips other-env modules. The ONLY config
    door.
    """    
    config = _load_config()
    env_names = tuple(config)
    applied = [name for name in env_names if request.node.get_closest_marker(name)]
    if len(applied) != 1:
        markers = " / ".join("@pytest.mark." + n for n in env_names)
        raise pytest.UsageError(
            f"{request.node.nodeid} must have exactly one environment marker "
            f"({markers}); found {applied}"
        )
    env_name = applied[0]

    selected = request.config.getoption("--env")
    if selected and selected != env_name:
        pytest.skip(f"--env={selected}; skipping {env_name} test")

    settings = config[env_name]
    client = ApiClient(
        base_url=settings["base_url"],
        max_response_time=settings["max_response_time"],
    )
    env = Environment(
        client=client,
        min_results_count=settings["min_results_count"],
        max_response_time=settings["max_response_time"],
    )
    yield env
    client.close()  # close the pooled session after the test
