import pytest

from cv_tailor.delivery.filenames import FALLBACK_FILENAME, build_filename


@pytest.mark.parametrize(
    ("contact_name", "expected"),
    [
        ("Ahmed Mohamed Abdelsalam", "Ahmed_Abdelsalam_Resume.pdf"),
        ("Jordan Rivera", "Jordan_Rivera_Resume.pdf"),
        ("  Ahmed   Mohamed   Ali   Abdelsalam ", "Ahmed_Abdelsalam_Resume.pdf"),
        ("Madonna", "Madonna_Resume.pdf"),
        ("Zoë O'Neil", "Zo_O_Neil_Resume.pdf"),
        ("../Evil Name/..", "Evil_Name_Resume.pdf"),
    ],
)
def test_filename_uses_first_and_last_name(contact_name: str, expected: str) -> None:
    assert build_filename(contact_name) == expected


@pytest.mark.parametrize("contact_name", ["", "   ", "أحمد محمد", "...", "///"])
def test_filename_falls_back_when_no_safe_characters_remain(contact_name: str) -> None:
    assert build_filename(contact_name) == FALLBACK_FILENAME
