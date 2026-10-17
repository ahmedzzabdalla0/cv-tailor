from io import BytesIO

from pypdf import PdfReader

from cv_tailor.models.master_cv import MasterCv
from cv_tailor.rendering.typst_renderer import count_pages, render_pdf

SPECIAL_TEXT = "Costs $5 #tag *bold* _under_ a@b.c <b>x</b> ~tilde~ [brackets] 100% done"


def extract_text(pdf: bytes) -> str:
    reader = PdfReader(BytesIO(pdf))
    return " ".join(" ".join((page.extract_text() or "").split()) for page in reader.pages)


def test_output_is_a_pdf(master_cv: MasterCv) -> None:
    assert render_pdf(master_cv).startswith(b"%PDF")


def test_sample_cv_fits_two_pages(master_cv: MasterCv) -> None:
    assert count_pages(render_pdf(master_cv)) <= 2


def test_special_characters_render_literally(master_cv: MasterCv) -> None:
    first = master_cv.experience[0].model_copy(update={"bullets": [SPECIAL_TEXT]})
    cv = master_cv.model_copy(
        update={"summary": SPECIAL_TEXT, "experience": [first, *master_cv.experience[1:]]}
    )
    text = extract_text(render_pdf(cv))
    assert text.count(SPECIAL_TEXT) == 2


def test_contact_and_immutable_fields_are_rendered(master_cv: MasterCv) -> None:
    text = extract_text(render_pdf(master_cv))
    assert master_cv.contact.name in text
    assert master_cv.experience[0].company.upper() in text
    assert master_cv.education[0].institution.upper() in text


def test_long_content_produces_more_than_one_page(master_cv: MasterCv) -> None:
    bullets = ["Maintained a long running service with careful monitoring and tuning."] * 60
    cv = master_cv.model_copy(
        update={"experience": [master_cv.experience[0].model_copy(update={"bullets": bullets})]}
    )
    assert count_pages(render_pdf(cv)) > 1


def test_rendering_is_deterministic(master_cv: MasterCv) -> None:
    assert extract_text(render_pdf(master_cv)) == extract_text(render_pdf(master_cv))
