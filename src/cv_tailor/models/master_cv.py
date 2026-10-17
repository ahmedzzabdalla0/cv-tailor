from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from cv_tailor.errors import ConfigurationError, describe_validation_error


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Contact(FrozenModel):
    name: str
    email: str
    phone: str
    location: str
    links: list[str] = Field(default_factory=list)


class SkillGroup(FrozenModel):
    group: str
    items: list[str]


class Entry(FrozenModel):
    id: str
    bullets: list[str]


class ExperienceEntry(Entry):
    company: str
    role: str
    location: str
    start: str
    end: str


class ProjectEntry(Entry):
    name: str
    link: str | None = None
    tech: list[str] = Field(default_factory=list)


class EducationEntry(FrozenModel):
    institution: str
    degree: str
    start: str
    end: str


class MasterCv(FrozenModel):
    contact: Contact
    summary: str
    skills: list[SkillGroup]
    experience: list[ExperienceEntry]
    projects: list[ProjectEntry]
    education: list[EducationEntry]
    certifications: list[str]


def load_master_cv(inline_json: str | None, path: Path) -> MasterCv:
    raw = inline_json if inline_json is not None else _read_file(path)
    try:
        return MasterCv.model_validate_json(raw)
    except ValidationError as error:
        raise ConfigurationError(describe_validation_error("master CV", error)) from None


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigurationError(f"cannot read master CV file: {path}") from error
