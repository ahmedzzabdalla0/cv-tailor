import json
from pathlib import Path

import pytest

from cv_tailor.delivery.base import Deliverable
from cv_tailor.delivery.local_files import LocalFilesChannel
from cv_tailor.errors import DeliveryError
from cv_tailor.models.master_cv import MasterCv
from tests.factories import build_job
from tests.fakes import valid_content


def build_deliverable(master: MasterCv) -> Deliverable:
    return Deliverable(
        job=build_job("job-9"),
        contact_name=master.contact.name,
        pdf=b"%PDF-fake",
        content=valid_content(master),
        warnings=[],
    )


def test_pdf_and_tailored_json_are_written(tmp_path: Path, master_cv: MasterCv) -> None:
    output_dir = tmp_path / "nested" / "out"
    LocalFilesChannel(output_dir).deliver_success(build_deliverable(master_cv))
    assert (output_dir / "job-9.pdf").read_bytes() == b"%PDF-fake"
    saved = json.loads((output_dir / "job-9.tailored.json").read_text(encoding="utf-8"))
    assert saved["summary"] == master_cv.summary


def test_unwritable_directory_raises_delivery_error(tmp_path: Path, master_cv: MasterCv) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(DeliveryError):
        LocalFilesChannel(blocker / "out").deliver_success(build_deliverable(master_cv))


def test_failure_notice_writes_nothing(tmp_path: Path) -> None:
    LocalFilesChannel(tmp_path / "out").deliver_failure(build_job(), "reason")
    assert not (tmp_path / "out").exists()
