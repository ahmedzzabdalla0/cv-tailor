import logging
from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from cv_tailor.delivery.base import Deliverable, DeliveryChannel
from cv_tailor.errors import DeliveryError, JobFailedError, RenderingError, TailoringError
from cv_tailor.models.job import Job
from cv_tailor.models.master_cv import MasterCv
from cv_tailor.models.tailoring import BatchResponse, TailoredContent, apply_tailoring
from cv_tailor.rendering.typst_renderer import count_pages, render_pdf
from cv_tailor.tailoring.guard import find_violations

logger = logging.getLogger(__name__)


class AiClient(Protocol):
    def tailor_batch(self, jobs: Sequence[Job]) -> BatchResponse: ...

    def tailor_single(self, job: Job, violations: Sequence[str]) -> TailoredContent: ...


class JobOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    succeeded: bool
    reason: str | None = None


def chunk[T](items: Sequence[T], size: int) -> list[Sequence[T]]:
    return [items[start : start + size] for start in range(0, len(items), size)]


def exit_code(outcomes: Sequence[JobOutcome]) -> int:
    return 0 if all(outcome.succeeded for outcome in outcomes) else 1


class Pipeline:
    def __init__(
        self,
        master: MasterCv,
        ai: AiClient,
        channels: Sequence[DeliveryChannel],
        batch_size: int,
        max_projects: int,
        guard_retry_limit: int,
    ) -> None:
        self._master = master
        self._ai = ai
        self._channels = channels
        self._batch_size = batch_size
        self._max_projects = max_projects
        self._guard_retry_limit = guard_retry_limit

    def run(self, jobs: Sequence[Job]) -> list[JobOutcome]:
        outcomes = [
            outcome for batch in chunk(jobs, self._batch_size) for outcome in self._run_batch(batch)
        ]
        failed = sum(1 for outcome in outcomes if not outcome.succeeded)
        logger.info("finished: %d succeeded, %d failed", len(outcomes) - failed, failed)
        return outcomes

    def _run_batch(self, batch: Sequence[Job]) -> list[JobOutcome]:
        results = self._request_batch(batch)
        return [self._run_job(job, results.get(job.job_id)) for job in batch]

    def _request_batch(self, batch: Sequence[Job]) -> dict[str, TailoredContent]:
        try:
            response = self._ai.tailor_batch(batch)
        except TailoringError as error:
            logger.error("batch request failed: %s", error)
            return {}
        return {result.job_id: result.content for result in response.results}

    def _run_job(self, job: Job, content: TailoredContent | None) -> JobOutcome:
        try:
            self._deliver(self._build_deliverable(job, content))
        except JobFailedError as error:
            return self._fail(job, error.reason)
        except Exception as error:
            logger.error("job %s failed unexpectedly: %s", job.job_id, type(error).__name__)
            return self._fail(job, "unexpected error")
        logger.info("job %s succeeded", job.job_id)
        return JobOutcome(job_id=job.job_id, succeeded=True)

    def _build_deliverable(self, job: Job, content: TailoredContent | None) -> Deliverable:
        valid_content = self._validated(job, content)
        pdf = self._render(apply_tailoring(self._master, valid_content))
        pages = count_pages(pdf)
        warnings = [f"Warning: the CV spans {pages} pages instead of one."] if pages > 1 else []
        return Deliverable(
            job=job,
            contact_name=self._master.contact.name,
            pdf=pdf,
            content=valid_content,
            warnings=warnings,
        )

    def _validated(self, job: Job, content: TailoredContent | None) -> TailoredContent:
        if content is None:
            raise JobFailedError("the model returned no result")
        violations = find_violations(self._master, content, self._max_projects)
        retries = 0
        while violations and retries < self._guard_retry_limit:
            retries += 1
            logger.warning("job %s has %d guard violations", job.job_id, len(violations))
            content = self._correct(job, violations)
            violations = find_violations(self._master, content, self._max_projects)
        if violations:
            raise JobFailedError("the content guard rejected the result")
        return content

    def _correct(self, job: Job, violations: Sequence[str]) -> TailoredContent:
        try:
            return self._ai.tailor_single(job, violations)
        except TailoringError as error:
            logger.error("corrective request for %s failed: %s", job.job_id, error)
            raise JobFailedError("the model request failed") from None

    def _render(self, cv: MasterCv) -> bytes:
        try:
            return render_pdf(cv)
        except RenderingError:
            raise JobFailedError("rendering failed") from None

    def _deliver(self, deliverable: Deliverable) -> None:
        failures = 0
        for channel in self._channels:
            try:
                channel.deliver_success(deliverable)
            except DeliveryError as error:
                failures += 1
                logger.error("delivery of %s failed: %s", deliverable.job.job_id, error)
        if failures:
            raise JobFailedError("delivery failed")

    def _fail(self, job: Job, reason: str) -> JobOutcome:
        logger.error("job %s failed: %s", job.job_id, reason)
        for channel in self._channels:
            try:
                channel.deliver_failure(job, reason)
            except DeliveryError as error:
                logger.error("failure notice for %s not delivered: %s", job.job_id, error)
        return JobOutcome(job_id=job.job_id, succeeded=False, reason=reason)
