import logging
from pathlib import Path

from cv_tailor.delivery.base import Deliverable
from cv_tailor.errors import DeliveryError
from cv_tailor.models.job import Job

logger = logging.getLogger(__name__)


class LocalFilesChannel:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def deliver_success(self, deliverable: Deliverable) -> None:
        job_id = deliverable.job.job_id
        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            (self._output_dir / f"{job_id}.pdf").write_bytes(deliverable.pdf)
            (self._output_dir / f"{job_id}.tailored.json").write_text(
                deliverable.content.model_dump_json(indent=2), encoding="utf-8"
            )
        except OSError:
            raise DeliveryError("could not write output files") from None
        logger.info("wrote %s to %s", job_id, self._output_dir)

    def deliver_failure(self, job: Job, reason: str) -> None:
        return None
