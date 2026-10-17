from pathlib import Path

import pytest
from pydantic import ValidationError

from cv_tailor.settings import Settings

MANAGED = [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_TEMPERATURE",
    "BATCH_SIZE",
    "DELIVERY",
    "JOBS_JSON",
    "MASTER_CV_JSON",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in MANAGED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def test_model_and_key_are_required() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings()
    missing = {error["loc"][0] for error in caught.value.errors()}
    assert missing == {"gemini_api_key", "gemini_model"}


def test_defaults_match_specification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "some-model")
    settings = Settings()
    assert settings.gemini_temperature == 0.2
    assert settings.gemini_timeout_seconds == 120
    assert settings.batch_size == 3
    assert settings.max_description_chars == 6000
    assert settings.max_projects == 3
    assert settings.guard_retry_limit == 1
    assert settings.delivery == "local"
    assert settings.output_dir == Path("out")
    assert settings.master_cv_path == Path("data/master_cv.json")


def test_telegram_delivery_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "some-model")
    monkeypatch.setenv("DELIVERY", "both")
    with pytest.raises(ValidationError, match="telegram_bot_token"):
        Settings()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    assert Settings().telegram_credentials == ("token", "chat")


def test_empty_environment_values_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "some-model")
    monkeypatch.setenv("JOBS_JSON", "")
    monkeypatch.setenv("MASTER_CV_JSON", "")
    settings = Settings()
    assert settings.jobs_json is None
    assert settings.master_cv_json is None


def test_secrets_are_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "some-model")
    assert "super-secret-key" not in repr(Settings())
