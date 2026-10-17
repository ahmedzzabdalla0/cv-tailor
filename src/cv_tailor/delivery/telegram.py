import json
import logging
import re
import time
from collections.abc import Callable

import requests
from pydantic import BaseModel, ValidationError

from cv_tailor.delivery.base import Deliverable
from cv_tailor.errors import DeliveryError
from cv_tailor.models.job import Job

logger = logging.getLogger(__name__)

API_ROOT = "https://api.telegram.org"
CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096
REASON_LIMIT = 200
RATE_LIMIT_STATUS = 429
UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
UNSAFE_REASON_CHARS = re.compile(r"[^A-Za-z0-9 .,:;@()/-]")


class RetryParameters(BaseModel):
    retry_after: int = 1


class TelegramError(BaseModel):
    description: str = ""
    parameters: RetryParameters = RetryParameters()


def build_filename(contact_name: str, company: str) -> str:
    return f"{_sanitize_part(contact_name)}_CV_{_sanitize_part(company)}.pdf"


def build_caption(job: Job, warnings: list[str]) -> str:
    return "\n".join([f"{job.title} @ {job.company}", *warnings])[:CAPTION_LIMIT]


def _sanitize_part(text: str) -> str:
    return UNSAFE_FILENAME_CHARS.sub("_", text).strip("_")


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
        filename = build_filename(deliverable.contact_name, job.company)
        data = {**self._base_data(job), "caption": build_caption(job, deliverable.warnings)}
        files = {"document": (filename, deliverable.pdf, "application/pdf")}
        self._post("sendDocument", data, files)
        logger.info("sent %s to telegram", job.job_id)

    def deliver_failure(self, job: Job, reason: str) -> None:
        safe_reason = UNSAFE_REASON_CHARS.sub("", reason)[:REASON_LIMIT]
        text = f"Could not tailor a CV for {job.title} @ {job.company}: {safe_reason}"
        self._post("sendMessage", {**self._base_data(job), "text": text[:MESSAGE_LIMIT]}, None)

    def _base_data(self, job: Job) -> dict[str, str]:
        data = {"chat_id": self._chat_id}
        if job.telegram_message_id is not None:
            data["reply_parameters"] = json.dumps(
                {"message_id": job.telegram_message_id, "allow_sending_without_reply": True}
            )
        return data

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
