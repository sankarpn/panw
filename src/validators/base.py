"""Shared assertion vocabulary used by tests across both APIs.

Schema validation lives in the per-contract pydantic models (one class per API
contract). These helpers are the value-level checks (count/range) that the tests
share — kept here so the two suites speak the same assertion language.
"""


def assert_min_count(seq, *, threshold, label="result count") -> None:
    """Assert len(seq) >= threshold, with a diagnostic message."""
    count = len(seq)
    assert count >= threshold, f"{label}: {count} below required minimum {threshold}"


def assert_in_range(value, low, high, *, label="value") -> None:
    """Assert low <= value <= high, with a diagnostic message."""
    assert low <= value <= high, f"{label}: {value} outside [{low}, {high}]"
