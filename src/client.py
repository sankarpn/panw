import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SLAViolation(AssertionError):
    """An API response took longer than the environment's max_response_time."""


class StatusMismatch(AssertionError):
    """A response's status code did not match the expected status."""


class TransportError(RuntimeError):
    """A request failed at the transport layer (after retries) — not an HTTP status."""


# Transient statuses worth retrying for idempotent GETs (load/maintenance/throttle).
_RETRY_STATUSES = (429, 500, 502, 503, 504)


class ApiClient:
    """Pooled HTTP client that retries transient failures, enforces the
    per-environment response-time SLA, and checks the expected status.

    Thresholds come from environments.yaml via the env fixture; test bodies never
    see or hardcode them. Per-API knobs (timeout/retries/headers/auth) are
    constructor config, so adding a new API needs no edit to this class.
    """

    def __init__(
        self,
        base_url,
        max_response_time,
        *,
        timeout=10.0,
        retries=2,
        backoff_factor=0.3,
        headers=None,
        auth=None,
        pool_maxsize=20,
    ):
        self._base_url = base_url.rstrip("/")
        self._max_response_time = max_response_time
        # Hard transport ceiling. Keep ABOVE max_response_time so a slow-but-
        # completed response is reported as an SLA breach (with its elapsed time),
        # not aborted as a timeout.
        self._timeout = timeout
        self._session = self._build_session(
            retries, backoff_factor, headers, auth, pool_maxsize
        )

    @staticmethod
    def _build_session(retries, backoff_factor, headers, auth, pool_maxsize):
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,        # exponential: 0, bf, 2*bf, ...
            status_forcelist=_RETRY_STATUSES,
            allowed_methods=frozenset({"GET"}),   # only retry idempotent verbs
            respect_retry_after_header=True,      # honor 429 Retry-After
            raise_on_status=False,                # our status check handles mismatches
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=pool_maxsize)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        if headers:
            session.headers.update(headers)
        if auth:
            session.auth = auth
        return session

    def get(self, path, *, expect_status=200, **kwargs):
        return self.request("GET", path, expect_status=expect_status, **kwargs)

    def request(self, method, path, *, expect_status=200, **kwargs):
        url = f"{self._base_url}/{path.lstrip('/')}"
        kwargs.setdefault("timeout", self._timeout)
        logger.info("%s %s params=%s", method, url, kwargs.get("params"))
        try:
            response = self._session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            # Retries already exhausted by the adapter; surface with context.
            raise TransportError(f"{method} {url} failed: {exc}") from exc
        elapsed = response.elapsed.total_seconds()
        logger.info("  -> %s in %.3fs", response.status_code, elapsed)
        if elapsed > self._max_response_time:
            raise SLAViolation(
                f"{url} responded in {elapsed:.3f}s, exceeding the "
                f"max_response_time of {self._max_response_time}s"
            )
        if response.status_code != expect_status:
            raise StatusMismatch(
                f"{url} returned {response.status_code}, expected {expect_status}"
            )
        return response

    def close(self):
        self._session.close()
