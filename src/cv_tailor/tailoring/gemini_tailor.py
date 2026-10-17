import logging
import time
from collections.abc import Callable, Sequence

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from cv_tailor.errors import TailoringError
from cv_tailor.models.job import Job
from cv_tailor.models.master_cv import MasterCv
from cv_tailor.models.tailoring import BatchResponse, TailoredContent
from cv_tailor.tailoring.prompt_builder import (
    build_batch_prompt,
    build_correction_prompt,
    build_system_instruction,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 1.0
SERVER_ERROR_FLOOR = 500
RATE_LIMIT_CODE = 429


def call_with_retries[T](
    operation: Callable[[], T],
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return operation()
        except errors.APIError as error:
            if not _is_transient(error.code) or attempt == MAX_ATTEMPTS:
                raise TailoringError(f"gemini request failed with status {error.code}") from None
            logger.warning("gemini transient error %s, attempt %d", error.code, attempt)
            sleep(BASE_DELAY_SECONDS * 2 ** (attempt - 1))
    raise TailoringError("gemini request failed")


def _is_transient(code: int) -> bool:
    return code == RATE_LIMIT_CODE or code >= SERVER_ERROR_FLOOR


class GeminiTailor:
    def __init__(
        self,
        client: genai.Client,
        master: MasterCv,
        model: str,
        temperature: float,
        timeout_seconds: int,
        max_projects: int,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._master = master
        self._model = model
        self._temperature = temperature
        self._timeout_milliseconds = timeout_seconds * 1000
        self._system_instruction = build_system_instruction(max_projects)
        self._sleep = sleep

    def tailor_batch(self, jobs: Sequence[Job]) -> BatchResponse:
        prompt = build_batch_prompt(self._master, jobs)
        return self._generate(prompt, BatchResponse)

    def tailor_single(self, job: Job, violations: Sequence[str]) -> TailoredContent:
        prompt = build_correction_prompt(self._master, job, violations)
        return self._generate(prompt, TailoredContent)

    def _generate[M: BaseModel](self, prompt: str, schema: type[M]) -> M:
        config = types.GenerateContentConfig(
            system_instruction=self._system_instruction,
            temperature=self._temperature,
            response_mime_type="application/json",
            response_schema=schema,
            http_options=types.HttpOptions(timeout=self._timeout_milliseconds),
        )
        response = call_with_retries(
            lambda: self._client.models.generate_content(
                model=self._model, contents=prompt, config=config
            ),
            self._sleep,
        )
        return _parse(response.text, schema)


def _parse[M: BaseModel](text: str | None, schema: type[M]) -> M:
    if not text:
        raise TailoringError("gemini returned an empty response")
    try:
        return schema.model_validate_json(text)
    except ValidationError:
        raise TailoringError("gemini returned output that does not match the schema") from None
