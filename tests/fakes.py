from collections.abc import Callable, Sequence

from cv_tailor.delivery.base import Deliverable
from cv_tailor.errors import DeliveryError
from cv_tailor.models.job import Job
from cv_tailor.models.master_cv import MasterCv
from cv_tailor.models.tailoring import BatchResponse, JobResult, TailoredContent, mutable_view

BatchFactory = Callable[[Sequence[Job]], BatchResponse]
SingleFactory = Callable[[Job, Sequence[str]], TailoredContent]


def valid_content(master: MasterCv, max_projects: int = 3) -> TailoredContent:
    view = mutable_view(master)
    return view.model_copy(update={"projects": view.projects[:max_projects]})


class FakeAi:
    def __init__(
        self,
        master: MasterCv,
        batch: BatchFactory | None = None,
        single: SingleFactory | None = None,
    ) -> None:
        self._valid = valid_content(master)
        self._batch = batch
        self._single = single
        self.batch_calls: list[list[str]] = []
        self.single_calls: list[tuple[str, list[str]]] = []

    def tailor_batch(self, jobs: Sequence[Job]) -> BatchResponse:
        self.batch_calls.append([job.job_id for job in jobs])
        if self._batch is not None:
            return self._batch(jobs)
        return BatchResponse(
            results=[JobResult(job_id=job.job_id, content=self._valid) for job in jobs]
        )

    def tailor_single(self, job: Job, violations: Sequence[str]) -> TailoredContent:
        self.single_calls.append((job.job_id, list(violations)))
        if self._single is not None:
            return self._single(job, violations)
        return self._valid


class RecordingChannel:
    def __init__(self, failing_job_ids: frozenset[str] = frozenset()) -> None:
        self._failing_job_ids = failing_job_ids
        self.delivered: list[Deliverable] = []
        self.failures: list[tuple[str, str]] = []

    def deliver_success(self, deliverable: Deliverable) -> None:
        if deliverable.job.job_id in self._failing_job_ids:
            raise DeliveryError("channel is down")
        self.delivered.append(deliverable)

    def deliver_failure(self, job: Job, reason: str) -> None:
        self.failures.append((job.job_id, reason))
