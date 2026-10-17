from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from cv_tailor.errors import ConfigurationError, describe_validation_error


class Job(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str = Field(pattern=r"^[A-Za-z0-9_-][A-Za-z0-9_.-]*$")
    title: str
    company: str
    description: str
    url: str | None = None
    score: float | None = None
    telegram_message_id: int | None = None


JOBS_ADAPTER = TypeAdapter(list[Job])


def parse_jobs(raw_json: str, max_description_chars: int) -> list[Job]:
    try:
        jobs = JOBS_ADAPTER.validate_json(raw_json)
    except ValidationError as error:
        raise ConfigurationError(describe_validation_error("jobs", error)) from None
    return [_truncate(job, max_description_chars) for job in _drop_duplicates(jobs)]


def _drop_duplicates(jobs: Iterable[Job]) -> list[Job]:
    unique: dict[str, Job] = {}
    for job in jobs:
        unique.setdefault(job.job_id, job)
    return list(unique.values())


def _truncate(job: Job, max_description_chars: int) -> Job:
    return job.model_copy(update={"description": job.description[:max_description_chars]})


def load_jobs(inline_json: str | None, path: Path | None, max_description_chars: int) -> list[Job]:
    if inline_json is not None:
        return parse_jobs(inline_json, max_description_chars)
    if path is None:
        raise ConfigurationError("provide a jobs file with --jobs-file or set JOBS_JSON")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigurationError(f"cannot read jobs file: {path}") from error
    return parse_jobs(raw, max_description_chars)
