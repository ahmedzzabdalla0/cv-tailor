from typing import Protocol

from pydantic import BaseModel, ConfigDict

from cv_tailor.models.job import Job
from cv_tailor.models.tailoring import TailoredContent


class Deliverable(BaseModel):
    model_config = ConfigDict(frozen=True)

    job: Job
    contact_name: str
    pdf: bytes
    content: TailoredContent
    warnings: list[str]


class DeliveryChannel(Protocol):
    def deliver_success(self, deliverable: Deliverable) -> None: ...

    def deliver_failure(self, job: Job, reason: str) -> None: ...
