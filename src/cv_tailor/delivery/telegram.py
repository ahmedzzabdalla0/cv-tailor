import json
import logging
import re
import time
from collections.abc import Callable

import requests
from pydantic import BaseModel, ValidationError

from cv_tailor.delivery.base import Deliverable
from cv_tailor.delivery.filenames import build_filename
from cv_tailor.errors import DeliveryError
from cv_tailor.models.job import Job

logger = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
REASON_LIMIT = 200
DESCRIPTION_SEPARATOR = "\n\n"
ELLIPSIS = "..."
RATE_LIMIT_STATUS = 429
UNSAFE_REASON_CHARS = re.compile(r"[^A-Za-z0-9 .,:;@()/-]")


class RetryParameters(BaseModel):
    retry_after: int = 1


class TelegramError(BaseModel):
    description: str = ""
    parameters: RetryParameters = RetryParameters()


def build_caption(job: Job, warnings: list[str]) -> str:
    return "\n".join([f"{job.title} @ {job.company}", *warnings])[:CAPTION_LIMIT]


def build_standalone_caption(job: Job, warnings: list[str]) -> str:
    header_lines = [f"{job.title} @ {job.company}"]
    if job.score is not None:
        header_lines.append(f"Score: {job.score:g}%")
    if job.url:
        header_lines.append(f"Link: {job.url}")
    header = "\n".join([*header_lines, *warnings])
    remaining = CAPTION_LIMIT - len(header) - len(DESCRIPTION_SEPARATOR)
    description = " ".join(job.description.split())
    if remaining <= len(ELLIPSIS) or not description:
        return header[:CAPTION_LIMIT]
    if len(description) > remaining:
        description = description[: remaining - len(ELLIPSIS)].rstrip() + ELLIPSIS
    return f"{header}{DESCRIPTION_SEPARATOR}{description}"


class TelegramChannel:
    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout_seconds: int = 30,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_seconds = timeout_seconds
        self._sleep = sleep

    def deliver_success(self, deliverable: Deliverable) -> None:
        job = deliverable.job
        filename = build_filename(deliverable.contact_name)
        files = {"document": (filename, deliverable.pdf, "application/pdf")}
        replied = self._deliver(
            "sendDocument",
            job,
            reply_fields={"caption": build_caption(job, deliverable.warnings)},
            standalone_fields={"caption": build_standalone_caption(job, deliverable.warnings)},
            files=files,
        )
        logger.info("sent %s to telegram %s", job.job_id, "as a reply" if replied else "standalone")

    def deliver_failure(self, job: Job, reason: str) -> None:
        safe_reason = UNSAFE_REASON_CHARS.sub("", reason)[:REASON_LIMIT]
        text = f"Could not tailor a CV for {job.title} @ {job.company}: {safe_reason}"
        fields = {"text": text[:MESSAGE_LIMIT]}
        self._deliver("sendMessage", job, reply_fields=fields, standalone_fields=fields, files=None)

    def _deliver(
        self,
        method: str,
        job: Job,
        reply_fields: dict[str, str],
        standalone_fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None,
    ) -> bool:
        if job.telegram_message_id is not None:
            reply_data = {
                "chat_id": self._chat_id,
                **reply_fields,
                "reply_parameters": json.dumps({"message_id": job.telegram_message_id}),
            }
            try:
                self._post(method, reply_data, files)
            except DeliveryError as error:
                logger.warning("reply for %s failed, sending standalone: %s", job.job_id, error)
            else:
                return True
        self._post(method, {"chat_id": self._chat_id, **standalone_fields}, files)
        return False

    def _post(
        self,
        method: str,
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None,
    ) -> None:
        response = self._send(method, data, files)
        if response.status_code == RATE_LIMIT_STATUS:
            self._sleep(_parse_error(response).parameters.retry_after)
            response = self._send(method, data, files)
        if not response.ok:
            description = _parse_error(response).description
            raise DeliveryError(
                f"telegram {method} failed with status {response.status_code}: {description}"
            )

    def _send(
        self,
        method: str,
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None,
    ) -> requests.Response:
        url = f"{API_ROOT}/bot{self._bot_token}/{method}"
        try:
            return requests.post(url, data=data, files=files, timeout=self._timeout_seconds)
        except requests.RequestException:
            raise DeliveryError(f"telegram {method} request failed") from None


def _parse_error(response: requests.Response) -> TelegramError:
    try:
        return TelegramError.model_validate_json(response.text)
    except ValidationError:
        return TelegramError()
