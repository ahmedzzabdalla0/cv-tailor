import json

import pytest

from cv_tailor.errors import ConfigurationError
from cv_tailor.models.job import parse_jobs


def raw_jobs(*jobs: dict[str, object]) -> str:
    return json.dumps(list(jobs))


def job_dict(job_id: str, description: str = "text") -> dict[str, object]:
    return {"job_id": job_id, "title": "Engineer", "company": "Initech", "description": description}


def test_valid_jobs_are_parsed_with_optional_fields() -> None:
    jobs = parse_jobs(raw_jobs({**job_dict("a"), "url": "https://example.com", "score": 0.5}), 100)
    assert [job.job_id for job in jobs] == ["a"]
    assert jobs[0].url == "https://example.com"
    assert jobs[0].telegram_message_id is None


def test_duplicate_job_ids_keep_first_occurrence() -> None:
    jobs = parse_jobs(raw_jobs(job_dict("a", "first"), job_dict("b"), job_dict("a", "second")), 100)
    assert [(job.job_id, job.description) for job in jobs] == [("a", "first"), ("b", "text")]


def test_description_is_truncated() -> None:
    jobs = parse_jobs(raw_jobs(job_dict("a", "x" * 50)), 10)
    assert jobs[0].description == "x" * 10


def test_missing_field_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="invalid jobs"):
        parse_jobs(json.dumps([{"job_id": "a"}]), 100)


def test_unsafe_job_id_is_rejected() -> None:
    with pytest.raises(ConfigurationError):
        parse_jobs(raw_jobs(job_dict("../escape")), 100)


def test_error_message_does_not_echo_input_values() -> None:
    secret = "super-secret-description"
    with pytest.raises(ConfigurationError) as caught:
        parse_jobs(json.dumps([{"job_id": 5, "description": secret}]), 100)
    assert secret not in str(caught.value)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (42, 42),
        ("42", 42),
        (" 42 ", 42),
        (42.0, 42),
        (None, None),
        (0, None),
        (-5, None),
        ("abc", None),
        ("", None),
        (4.5, None),
        (True, None),
        ([1], None),
        ({"id": 1}, None),
    ],
)
def test_invalid_telegram_message_id_is_ignored_instead_of_failing_the_run(
    raw_value: object, expected: int | None
) -> None:
    jobs = parse_jobs(raw_jobs({**job_dict("a"), "telegram_message_id": raw_value}), 100)
    assert jobs[0].telegram_message_id == expected
