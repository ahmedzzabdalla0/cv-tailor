from collections.abc import Sequence

import pytest

from cv_tailor.errors import TailoringError
from cv_tailor.models.job import Job
from cv_tailor.models.master_cv import MasterCv
from cv_tailor.models.tailoring import (
    BatchResponse,
    JobResult,
    TailoredContent,
    TailoredSkillGroup,
)
from cv_tailor.pipeline import Pipeline, chunk, exit_code
from tests.factories import build_job
from tests.fakes import FakeAi, RecordingChannel, valid_content


def build_pipeline(
    master: MasterCv,
    ai: FakeAi,
    channel: RecordingChannel,
    batch_size: int = 3,
    guard_retry_limit: int = 1,
) -> Pipeline:
    return Pipeline(
        master=master,
        ai=ai,
        channels=[channel],
        batch_size=batch_size,
        max_projects=3,
        guard_retry_limit=guard_retry_limit,
    )


def invalid_content(master: MasterCv) -> TailoredContent:
    return valid_content(master).model_copy(
        update={"skills": [TailoredSkillGroup(group="Languages", items=["Rust"])]}
    )


def test_chunk_splits_into_batches_of_given_size() -> None:
    assert chunk([1, 2, 3, 4, 5, 6, 7], 3) == [[1, 2, 3], [4, 5, 6], [7]]


def test_chunk_of_nothing_is_empty() -> None:
    assert chunk([], 3) == []


def test_chunk_with_large_size_keeps_single_batch() -> None:
    assert chunk([1, 2], 10) == [[1, 2]]


def test_all_jobs_succeed_and_exit_code_is_zero(master_cv: MasterCv) -> None:
    ai, channel = FakeAi(master_cv), RecordingChannel()
    jobs = [build_job("a"), build_job("b"), build_job("c"), build_job("d")]
    outcomes = build_pipeline(master_cv, ai, channel).run(jobs)
    assert exit_code(outcomes) == 0
    assert ai.batch_calls == [["a", "b", "c"], ["d"]]
    assert [item.job.job_id for item in channel.delivered] == ["a", "b", "c", "d"]
    assert channel.delivered[0].pdf.startswith(b"%PDF")
    assert channel.delivered[0].contact_name == master_cv.contact.name


def test_missing_job_in_response_fails_only_that_job(master_cv: MasterCv) -> None:
    valid = valid_content(master_cv)

    def respond_without_b(jobs: Sequence[Job]) -> BatchResponse:
        return BatchResponse(
            results=[
                JobResult(job_id=job.job_id, content=valid) for job in jobs if job.job_id != "b"
            ]
        )

    ai = FakeAi(master_cv, batch=respond_without_b)
    channel = RecordingChannel()
    outcomes = build_pipeline(master_cv, ai, channel).run([build_job("a"), build_job("b")])
    assert [(o.job_id, o.succeeded) for o in outcomes] == [("a", True), ("b", False)]
    assert [item.job.job_id for item in channel.delivered] == ["a"]
    assert channel.failures == [("b", "the model returned no result")]
    assert exit_code(outcomes) == 1


def test_unknown_ids_in_response_are_ignored(master_cv: MasterCv) -> None:
    valid = valid_content(master_cv)

    def respond_with_extra(jobs: Sequence[Job]) -> BatchResponse:
        ids = [job.job_id for job in jobs] + ["ghost"]
        return BatchResponse(results=[JobResult(job_id=i, content=valid) for i in ids])

    channel = RecordingChannel()
    outcomes = build_pipeline(master_cv, FakeAi(master_cv, batch=respond_with_extra), channel).run(
        [build_job("a")]
    )
    assert exit_code(outcomes) == 0
    assert [item.job.job_id for item in channel.delivered] == ["a"]


def test_failed_batch_does_not_stop_later_batches(master_cv: MasterCv) -> None:
    valid = valid_content(master_cv)
    calls: list[str] = []

    def fail_first_batch(jobs: Sequence[Job]) -> BatchResponse:
        calls.append(jobs[0].job_id)
        if len(calls) == 1:
            raise TailoringError("gemini request failed with status 503")
        return BatchResponse(results=[JobResult(job_id=j.job_id, content=valid) for j in jobs])

    channel = RecordingChannel()
    pipeline = build_pipeline(master_cv, FakeAi(master_cv, batch=fail_first_batch), channel, 1)
    outcomes = pipeline.run([build_job("a"), build_job("b")])
    assert [(o.job_id, o.succeeded) for o in outcomes] == [("a", False), ("b", True)]
    assert exit_code(outcomes) == 1


def test_guard_violation_triggers_one_corrective_call(master_cv: MasterCv) -> None:
    bad = invalid_content(master_cv)

    def bad_batch(jobs: Sequence[Job]) -> BatchResponse:
        return BatchResponse(results=[JobResult(job_id=j.job_id, content=bad) for j in jobs])

    ai = FakeAi(master_cv, batch=bad_batch)
    channel = RecordingChannel()
    outcomes = build_pipeline(master_cv, ai, channel).run([build_job("a")])
    assert exit_code(outcomes) == 0
    assert len(ai.single_calls) == 1
    job_id, violations = ai.single_calls[0]
    assert job_id == "a"
    assert any("Rust" in violation for violation in violations)


def test_persistent_violation_fails_job_after_retry_limit(master_cv: MasterCv) -> None:
    bad = invalid_content(master_cv)

    def bad_batch(jobs: Sequence[Job]) -> BatchResponse:
        return BatchResponse(results=[JobResult(job_id=j.job_id, content=bad) for j in jobs])

    ai = FakeAi(master_cv, batch=bad_batch, single=lambda job, violations: bad)
    channel = RecordingChannel()
    outcomes = build_pipeline(master_cv, ai, channel).run([build_job("a"), build_job("b")])
    assert exit_code(outcomes) == 1
    assert len(ai.single_calls) == 2
    assert channel.delivered == []
    assert channel.failures[0] == ("a", "the content guard rejected the result")


def test_zero_retry_limit_skips_corrective_call(master_cv: MasterCv) -> None:
    bad = invalid_content(master_cv)

    def bad_batch(jobs: Sequence[Job]) -> BatchResponse:
        return BatchResponse(results=[JobResult(job_id=j.job_id, content=bad) for j in jobs])

    ai = FakeAi(master_cv, batch=bad_batch)
    outcomes = build_pipeline(master_cv, ai, RecordingChannel(), guard_retry_limit=0).run(
        [build_job("a")]
    )
    assert exit_code(outcomes) == 1
    assert ai.single_calls == []


def test_corrective_call_failure_fails_only_that_job(master_cv: MasterCv) -> None:
    bad = invalid_content(master_cv)
    valid = valid_content(master_cv)

    def mixed_batch(jobs: Sequence[Job]) -> BatchResponse:
        return BatchResponse(
            results=[
                JobResult(job_id=j.job_id, content=bad if j.job_id == "a" else valid) for j in jobs
            ]
        )

    def failing_single(job: Job, violations: Sequence[str]) -> TailoredContent:
        raise TailoringError("gemini request failed with status 500")

    ai = FakeAi(master_cv, batch=mixed_batch, single=failing_single)
    channel = RecordingChannel()
    outcomes = build_pipeline(master_cv, ai, channel).run([build_job("a"), build_job("b")])
    assert [(o.job_id, o.succeeded) for o in outcomes] == [("a", False), ("b", True)]


def test_delivery_failure_marks_job_failed_but_others_continue(master_cv: MasterCv) -> None:
    channel = RecordingChannel(failing_job_ids=frozenset({"a"}))
    outcomes = build_pipeline(master_cv, FakeAi(master_cv), channel).run(
        [build_job("a"), build_job("b")]
    )
    assert [(o.job_id, o.succeeded) for o in outcomes] == [("a", False), ("b", True)]
    assert [item.job.job_id for item in channel.delivered] == ["b"]
    assert channel.failures == [("a", "delivery failed")]


def test_multi_page_pdf_adds_warning_but_still_succeeds(master_cv: MasterCv) -> None:
    long_bullets = ["Maintained a long running service with careful monitoring and tuning."] * 70
    first = master_cv.experience[0].model_copy(update={"bullets": long_bullets})
    long_master = master_cv.model_copy(update={"experience": [first, *master_cv.experience[1:]]})
    channel = RecordingChannel()
    outcomes = build_pipeline(long_master, FakeAi(long_master), channel).run([build_job("a")])
    assert exit_code(outcomes) == 0
    assert any("pages" in warning for warning in channel.delivered[0].warnings)


@pytest.mark.parametrize(("succeeded", "expected"), [([True, True], 0), ([True, False], 1)])
def test_exit_code_depends_on_every_outcome(succeeded: list[bool], expected: int) -> None:
    from cv_tailor.pipeline import JobOutcome

    outcomes = [JobOutcome(job_id=str(i), succeeded=ok) for i, ok in enumerate(succeeded)]
    assert exit_code(outcomes) == expected
