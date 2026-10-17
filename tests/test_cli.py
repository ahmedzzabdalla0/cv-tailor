import json
from pathlib import Path

import pytest

from cv_tailor import cli
from cv_tailor.models.master_cv import MasterCv
from tests.conftest import DATA_DIR
from tests.fakes import FakeAi

MANAGED = [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "DELIVERY",
    "OUTPUT_DIR",
    "JOBS_JSON",
    "MASTER_CV_JSON",
    "MASTER_CV_PATH",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in MANAGED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.setenv("GEMINI_MODEL", "some-model")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("MASTER_CV_PATH", str(DATA_DIR / "master_cv.example.json"))
    monkeypatch.setattr(cli, "build_ai", lambda settings, master: FakeAi(master))
    return tmp_path


def write_jobs(directory: Path, *job_ids: str) -> Path:
    jobs = [
        {"job_id": job_id, "title": "Engineer", "company": "Initech", "description": "text"}
        for job_id in job_ids
    ]
    path = directory / "jobs.json"
    path.write_text(json.dumps(jobs), encoding="utf-8")
    return path


def test_local_run_writes_files_and_returns_zero(environment: Path) -> None:
    jobs_file = write_jobs(environment, "a", "b")
    assert cli.main(["--jobs-file", str(jobs_file)]) == 0
    assert sorted(path.name for path in (environment / "out").iterdir()) == [
        "a.pdf",
        "a.tailored.json",
        "b.pdf",
        "b.tailored.json",
    ]


def test_jobs_json_environment_overrides_jobs_file(
    environment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs_file = write_jobs(environment, "from-file")
    monkeypatch.setenv(
        "JOBS_JSON",
        json.dumps([{"job_id": "from-env", "title": "T", "company": "C", "description": "D"}]),
    )
    assert cli.main(["--jobs-file", str(jobs_file)]) == 0
    assert (environment / "out" / "from-env.pdf").exists()
    assert not (environment / "out" / "from-file.pdf").exists()


def test_master_cv_json_environment_overrides_path(
    environment: Path, monkeypatch: pytest.MonkeyPatch, master_cv: MasterCv
) -> None:
    renamed = master_cv.model_copy(
        update={"contact": master_cv.contact.model_copy(update={"name": "Env Person"})}
    )
    monkeypatch.setenv("MASTER_CV_JSON", renamed.model_dump_json())
    monkeypatch.setattr(cli, "build_ai", lambda settings, master: FakeAi(master))
    jobs_file = write_jobs(environment, "a")
    assert cli.main(["--jobs-file", str(jobs_file)]) == 0


def test_missing_jobs_source_fails_fast(environment: Path) -> None:
    assert cli.main([]) == 1


def test_invalid_master_cv_fails_fast(environment: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MASTER_CV_JSON", "{}")
    assert cli.main(["--jobs-file", str(write_jobs(environment, "a"))]) == 1


def test_telegram_delivery_without_credentials_fails_fast(environment: Path) -> None:
    jobs_file = write_jobs(environment, "a")
    assert cli.main(["--jobs-file", str(jobs_file), "--delivery", "telegram"]) == 1


def test_configuration_error_does_not_echo_secret_values(
    environment: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("MASTER_CV_JSON", '{"summary": "private-cv-text"}')
    cli.main(["--jobs-file", str(write_jobs(environment, "a"))])
    assert "private-cv-text" not in caplog.text
