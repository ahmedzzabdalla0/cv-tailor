from pydantic import BaseModel, ConfigDict

from cv_tailor.models.master_cv import MasterCv, SkillGroup


class FrozenSchema(BaseModel):
    model_config = ConfigDict(frozen=True)


class TailoredSkillGroup(FrozenSchema):
    group: str
    items: list[str]


class TailoredEntry(FrozenSchema):
    id: str
    bullets: list[str]


class TailoredContent(FrozenSchema):
    summary: str
    skills: list[TailoredSkillGroup]
    experience: list[TailoredEntry]
    projects: list[TailoredEntry]


class JobResult(FrozenSchema):
    job_id: str
    content: TailoredContent


class BatchResponse(FrozenSchema):
    results: list[JobResult]


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def mutable_view(master: MasterCv) -> TailoredContent:
    return TailoredContent(
        summary=master.summary,
        skills=[TailoredSkillGroup(group=g.group, items=g.items) for g in master.skills],
        experience=[TailoredEntry(id=e.id, bullets=e.bullets) for e in master.experience],
        projects=[TailoredEntry(id=p.id, bullets=p.bullets) for p in master.projects],
    )


def apply_tailoring(master: MasterCv, content: TailoredContent) -> MasterCv:
    canonical_items = {normalize(i): i for group in master.skills for i in group.items}
    tailored_items = {normalize(g.group): g.items for g in content.skills}
    experience_bullets = {e.id: e.bullets for e in content.experience}
    master_projects = {p.id: p for p in master.projects}
    skills = [
        SkillGroup(group=group.group, items=items)
        for group in master.skills
        if (items := _canonical(tailored_items.get(normalize(group.group), []), canonical_items))
    ]
    return master.model_copy(
        update={
            "summary": content.summary,
            "skills": skills,
            "experience": [
                e.model_copy(update={"bullets": experience_bullets[e.id]})
                for e in master.experience
            ],
            "projects": [
                master_projects[p.id].model_copy(update={"bullets": p.bullets})
                for p in content.projects
            ],
        }
    )


def _canonical(items: list[str], canonical_items: dict[str, str]) -> list[str]:
    return [canonical_items[normalize(item)] for item in items]
