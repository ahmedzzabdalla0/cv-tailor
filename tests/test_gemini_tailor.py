import pytest
from google.genai import errors

from cv_tailor.errors import TailoringError
from cv_tailor.tailoring.gemini_tailor import call_with_retries


class FlakyOperation:
    def __init__(self, failures: list[int]) -> None:
        self.failures = failures
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.failures:
            raise errors.APIError(self.failures.pop(0), {"error": {"message": "boom"}})
        return "ok"


def test_transient_errors_are_retried_with_exponential_backoff() -> None:
    delays: list[float] = []
    operation = FlakyOperation([429, 503])
    assert call_with_retries(operation, delays.append) == "ok"
    assert operation.calls == 3
    assert delays == [1.0, 2.0]


def test_gives_up_after_three_attempts() -> None:
    operation = FlakyOperation([500, 500, 500])
    with pytest.raises(TailoringError, match="status 500"):
        call_with_retries(operation, lambda _: None)
    assert operation.calls == 3


def test_client_errors_are_not_retried() -> None:
    operation = FlakyOperation([400])
    with pytest.raises(TailoringError, match="status 400"):
        call_with_retries(operation, lambda _: None)
    assert operation.calls == 1
