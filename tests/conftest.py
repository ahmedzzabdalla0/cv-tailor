from pathlib import Path

import pytest

from cv_tailor.models.master_cv import MasterCv

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def master_cv() -> MasterCv:
    raw = (DATA_DIR / "master_cv.example.json").read_text(encoding="utf-8")
    return MasterCv.model_validate_json(raw)
