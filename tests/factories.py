from cv_tailor.models.job import Job


def build_job(job_id: str = "job-1", /, **overrides: object) -> Job:
    fields: dict[str, object] = {
        "job_id": job_id,
        "title": "Platform Developer",
        "company": "Initech",
        "description": "Build payment APIs in Python.",
        "telegram_message_id": 42,
    }
    fields.update(overrides)
    return Job.model_validate(fields)
