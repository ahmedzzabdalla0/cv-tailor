from functools import cache
from importlib.resources import files
from io import BytesIO

import typst
from pypdf import PdfReader

from cv_tailor.errors import RenderingError
from cv_tailor.models.master_cv import MasterCv


def render_pdf(cv: MasterCv) -> bytes:
    try:
        output = typst.compile(
            _read_template(),
            ignore_system_fonts=True,
            sys_inputs={"cv": cv.model_dump_json()},
        )
    except typst.TypstError:
        raise RenderingError("typst compilation failed") from None
    if not isinstance(output, bytes):
        raise RenderingError("typst produced no PDF output")
    return output


def count_pages(pdf: bytes) -> int:
    return len(PdfReader(BytesIO(pdf)).pages)


@cache
def _read_template() -> bytes:
    return files("cv_tailor.rendering").joinpath("templates/cv.typ").read_bytes()
