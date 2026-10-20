import json
import logging
import traceback

import pytest
import requests

from cv_tailor.delivery.base import Deliverable
from cv_tailor.delivery.telegram import (
    CAPTION_LIMIT,
    TelegramChannel,
    build_caption,
    build_standalone_caption,
)
from cv_tailor.errors import DeliveryError
from cv_tailor.models.master_cv import MasterCv
from tests.factories import build_job
from tests.fakes import valid_content

TOKEN = "123456:SECRET-TOKEN"


class FakeResponse:
    def __init__(self, status_code: int, body: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self.text = json.dumps(body or {})
        self.ok = status_code < 400


class PostRecorder:
    def __init__(self, *responses: FakeResponse | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], dict[str, tuple[str, bytes, str]] | None]] = []

    def __call__(
        self,
        url: str,
        *,
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]] | None,
        timeout: int,
    ) -> FakeResponse:
        self.calls.append((url, data, files))
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def build_deliverable(master: MasterCv, **job_overrides: object) -> Deliverable:
    return Deliverable(
        job=build_job(**job_overrides),
        contact_name=master.contact.name,
        pdf=b"%PDF-fake",
        content=valid_content(master),
        warnings=[],
    )


def install(monkeypatch: pytest.MonkeyPatch, recorder: PostRecorder) -> None:
    monkeypatch.setattr("requests.post", recorder)


def channel(sleeps: list[float] | None = None) -> TelegramChannel:
    recorded = sleeps if sleeps is not None else []
    return TelegramChannel(TOKEN, "999", sleep=recorded.append)


def test_document_is_sent_as_reply_with_resume_filename(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    recorder = PostRecorder(FakeResponse(200))
    install(monkeypatch, recorder)
    channel().deliver_success(build_deliverable(master_cv, company="Acme & Sons / Ltd"))
    assert len(recorder.calls) == 1
    url, data, files = recorder.calls[0]
    assert url.endswith("/sendDocument")
    assert data["chat_id"] == "999"
    assert json.loads(data["reply_parameters"]) == {"message_id": 42}
    assert data["caption"] == "Platform Developer @ Acme & Sons / Ltd"
    assert files is not None
    filename, content, mime = files["document"]
    assert filename == "Jordan_Rivera_Resume.pdf"
    assert content == b"%PDF-fake"
    assert mime == "application/pdf"


def test_no_reply_parameters_without_message_id(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    recorder = PostRecorder(FakeResponse(200))
    install(monkeypatch, recorder)
    channel().deliver_success(build_deliverable(master_cv, telegram_message_id=None))
    assert len(recorder.calls) == 1
    assert "reply_parameters" not in recorder.calls[0][1]
    assert "Build payment APIs in Python." in recorder.calls[0][1]["caption"]


@pytest.mark.parametrize(
    "failure",
    [
        FakeResponse(400, {"description": "Bad Request: message to be replied not found"}),
        FakeResponse(400, {"description": "Bad Request: message identifier is not specified"}),
        FakeResponse(500, {"description": "Internal Server Error"}),
        requests.ConnectionError("refused"),
    ],
    ids=["not-found", "invalid", "server-error", "network"],
)
def test_failed_reply_falls_back_to_standalone_document_with_job_details(
    monkeypatch: pytest.MonkeyPatch,
    master_cv: MasterCv,
    failure: FakeResponse | Exception,
) -> None:
    recorder = PostRecorder(failure, FakeResponse(200))
    install(monkeypatch, recorder)
    deliverable = build_deliverable(master_cv, url="https://example.com/jobs/1", score=87)
    channel().deliver_success(deliverable)
    assert len(recorder.calls) == 2
    reply_data, standalone_data = recorder.calls[0][1], recorder.calls[1][1]
    assert "reply_parameters" in reply_data
    assert "reply_parameters" not in standalone_data
    assert standalone_data["caption"].startswith(
        "Platform Developer @ Initech\nScore: 87%\nLink: https://example.com/jobs/1"
    )
    assert "Build payment APIs in Python." in standalone_data["caption"]
    standalone_files = recorder.calls[1][2]
    assert standalone_files is not None
    assert standalone_files["document"][0] == "Jordan_Rivera_Resume.pdf"
    assert standalone_files["document"][1] == b"%PDF-fake"


def test_failed_reply_and_failed_fallback_raise_delivery_error(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    recorder = PostRecorder(
        FakeResponse(400, {"description": "Bad Request: message to be replied not found"}),
        FakeResponse(400, {"description": "Bad Request: chat not found"}),
    )
    install(monkeypatch, recorder)
    with pytest.raises(DeliveryError, match="chat not found"):
        channel().deliver_success(build_deliverable(master_cv))
    assert len(recorder.calls) == 2


def test_standalone_caption_without_optional_fields_has_title_and_description() -> None:
    caption = build_standalone_caption(build_job(), [])
    assert caption == "Platform Developer @ Initech\n\nBuild payment APIs in Python."


def test_standalone_caption_keeps_warnings_and_respects_limit() -> None:
    job = build_job(description="word " * 1000, url="https://example.com/x", score=50.5)
    caption = build_standalone_caption(job, ["Warning: two pages"])
    assert len(caption) <= CAPTION_LIMIT
    assert "Score: 50.5%" in caption
    assert "Warning: two pages" in caption
    assert caption.endswith("...")


def test_standalone_caption_is_limited_when_header_alone_is_too_long() -> None:
    assert len(build_standalone_caption(build_job(), ["w" * 3000])) == CAPTION_LIMIT


def test_caption_has_title_company_and_warnings() -> None:
    job = build_job(title="Engineer", company="Initech")
    assert build_caption(job, ["Warning: two pages"]) == "Engineer @ Initech\nWarning: two pages"


def test_caption_is_limited_to_1024_characters() -> None:
    assert len(build_caption(build_job(), ["w" * 3000])) == 1024


def test_retry_after_is_honored_exactly_once(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    limited = FakeResponse(
        429, {"description": "Too Many Requests", "parameters": {"retry_after": 7}}
    )
    recorder = PostRecorder(limited, FakeResponse(200))
    install(monkeypatch, recorder)
    sleeps: list[float] = []
    channel(sleeps).deliver_success(build_deliverable(master_cv))
    assert sleeps == [7]
    assert len(recorder.calls) == 2


def test_second_rate_limit_raises_without_third_attempt(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    limited = FakeResponse(
        429, {"description": "Too Many Requests", "parameters": {"retry_after": 1}}
    )
    recorder = PostRecorder(limited, limited)
    install(monkeypatch, recorder)
    with pytest.raises(DeliveryError, match="status 429: Too Many Requests"):
        channel().deliver_success(build_deliverable(master_cv, telegram_message_id=None))
    assert len(recorder.calls) == 2


def test_error_reports_status_and_description_only(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    install(
        monkeypatch, PostRecorder(FakeResponse(400, {"description": "Bad Request: chat not found"}))
    )
    with pytest.raises(DeliveryError) as caught:
        channel().deliver_success(build_deliverable(master_cv, telegram_message_id=None))
    assert (
        str(caught.value)
        == "telegram sendDocument failed with status 400: Bad Request: chat not found"
    )
    assert TOKEN not in str(caught.value)


def test_network_error_never_leaks_token(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv, caplog: pytest.LogCaptureFixture
) -> None:
    leaky = requests.ConnectionError(f"HTTPSConnectionPool: /bot{TOKEN}/sendDocument refused")
    install(monkeypatch, PostRecorder(leaky, leaky))
    with caplog.at_level(logging.DEBUG), pytest.raises(DeliveryError) as caught:
        channel().deliver_success(build_deliverable(master_cv))
    assert TOKEN not in str(caught.value)
    assert TOKEN not in "".join(traceback.format_exception(caught.value))
    assert TOKEN not in caplog.text


def test_success_logging_never_contains_token(
    monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv, caplog: pytest.LogCaptureFixture
) -> None:
    install(monkeypatch, PostRecorder(FakeResponse(200)))
    with caplog.at_level(logging.DEBUG):
        channel().deliver_success(build_deliverable(master_cv))
    assert TOKEN not in caplog.text


def test_failed_job_gets_short_sanitized_text_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = PostRecorder(FakeResponse(200))
    install(monkeypatch, recorder)
    channel().deliver_failure(
        build_job(), "the content guard rejected <b>the</b> result\nTraceback"
    )
    url, data, files = recorder.calls[0]
    assert url.endswith("/sendMessage")
    assert files is None
    assert data["text"].startswith("Could not tailor a CV for Platform Developer @ Initech: ")
    assert "<" not in data["text"]
    assert "\n" not in data["text"]
    assert "reply_parameters" in data


def test_failed_job_notice_falls_back_to_plain_text_when_reply_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = PostRecorder(
        FakeResponse(400, {"description": "Bad Request: message to be replied not found"}),
        FakeResponse(200),
    )
    install(monkeypatch, recorder)
    channel().deliver_failure(build_job(), "rendering failed")
    assert len(recorder.calls) == 2
    assert "reply_parameters" not in recorder.calls[1][1]
    assert recorder.calls[1][1]["text"].startswith("Could not tailor a CV for")
