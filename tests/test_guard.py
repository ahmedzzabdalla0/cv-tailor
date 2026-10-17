import pytest

from cv_tailor.models.master_cv import MasterCv
from cv_tailor.models.tailoring import (
    TailoredContent,
    TailoredEntry,
    TailoredSkillGroup,
    mutable_view,
)
from cv_tailor.tailoring.guard import find_violations

MAX_PROJECTS = 3


@pytest.fixture
def valid_content(master_cv: MasterCv) -> TailoredContent:
    return mutable_view(master_cv).model_copy(
        update={"projects": mutable_view(master_cv).projects[:MAX_PROJECTS]}
    )


def test_valid_content_passes(master_cv: MasterCv, valid_content: TailoredContent) -> None:
    assert find_violations(master_cv, valid_content, MAX_PROJECTS) == []


def test_reordered_and_reduced_content_passes(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(
        update={
            "skills": [TailoredSkillGroup(group="Languages", items=["SQL", "Python"])],
            "projects": list(reversed(valid_content.projects))[:2],
            "summary": "Engineer focused on reliable payment APIs.",
        }
    )
    assert find_violations(master_cv, changed, MAX_PROJECTS) == []


def test_added_skill_is_reported(master_cv: MasterCv, valid_content: TailoredContent) -> None:
    changed = valid_content.model_copy(
        update={"skills": [TailoredSkillGroup(group="Languages", items=["Python", "Rust"])]}
    )
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("Rust" in violation for violation in violations)


def test_skill_check_is_case_and_whitespace_insensitive(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(
        update={
            "skills": [
                TailoredSkillGroup(group=" languages ", items=["PYTHON", "  github   actions"])
            ]
        }
    )
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert violations == []


def test_new_number_in_bullet_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    first, *rest = valid_content.experience
    inflated = TailoredEntry(id=first.id, bullets=[*first.bullets[:-1], "Handled 9,999 incidents."])
    changed = valid_content.model_copy(update={"experience": [inflated, *rest]})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("9,999" in violation for violation in violations)


def test_number_from_another_entry_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    first, second, *rest = valid_content.experience
    swapped = TailoredEntry(id=first.id, bullets=[*first.bullets[:-1], "Used by 35 agents."])
    changed = valid_content.model_copy(update={"experience": [swapped, second, *rest]})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("35" in violation for violation in violations)


def test_new_number_in_summary_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(update={"summary": "Engineer with 17 years of experience."})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("17" in violation for violation in violations)


def test_summary_may_reuse_numbers_from_anywhere_in_master(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(update={"summary": "Cut latency by 60% for 35 users."})
    assert find_violations(master_cv, changed, MAX_PROJECTS) == []


def test_overlong_summary_is_reported(master_cv: MasterCv, valid_content: TailoredContent) -> None:
    changed = valid_content.model_copy(update={"summary": "a" * 451})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("summary has 451" in violation for violation in violations)


def test_unknown_experience_id_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(
        update={
            "experience": [
                *valid_content.experience,
                TailoredEntry(id="exp-invented", bullets=["Did things."]),
            ]
        }
    )
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert "unknown experience id 'exp-invented'" in violations


def test_missing_experience_id_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(update={"experience": valid_content.experience[:1]})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert "missing experience id 'exp-globex'" in violations


def test_unknown_project_id_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    changed = valid_content.model_copy(
        update={"projects": [TailoredEntry(id="proj-invented", bullets=["Did things."])]}
    )
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert "unknown project id 'proj-invented'" in violations


def test_too_many_projects_is_reported(master_cv: MasterCv, valid_content: TailoredContent) -> None:
    changed = valid_content.model_copy(update={"projects": mutable_view(master_cv).projects})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert "4 projects selected, limit is 3" in violations


@pytest.mark.parametrize("bullet_count", [0, 5])
def test_bullet_count_out_of_range_is_reported(
    master_cv: MasterCv, valid_content: TailoredContent, bullet_count: int
) -> None:
    first, *rest = valid_content.experience
    changed_entry = TailoredEntry(id=first.id, bullets=["Maintained services."] * bullet_count)
    changed = valid_content.model_copy(update={"experience": [changed_entry, *rest]})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("allowed range is 2-4" in violation for violation in violations)


def test_bullet_count_within_one_of_master_passes(
    master_cv: MasterCv, valid_content: TailoredContent
) -> None:
    first, *rest = valid_content.experience
    shorter = TailoredEntry(id=first.id, bullets=first.bullets[:2])
    changed = valid_content.model_copy(update={"experience": [shorter, *rest]})
    assert find_violations(master_cv, changed, MAX_PROJECTS) == []


def test_empty_bullet_is_reported(master_cv: MasterCv, valid_content: TailoredContent) -> None:
    first, *rest = valid_content.experience
    blank = TailoredEntry(id=first.id, bullets=[*first.bullets[:-1], "   "])
    changed = valid_content.model_copy(update={"experience": [blank, *rest]})
    violations = find_violations(master_cv, changed, MAX_PROJECTS)
    assert any("empty bullet" in violation for violation in violations)
