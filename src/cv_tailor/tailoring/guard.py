import re
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence

from cv_tailor.models.master_cv import Entry, MasterCv
from cv_tailor.models.tailoring import TailoredContent, TailoredEntry, normalize

NUMERIC_TOKEN = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?%?")
MAX_SUMMARY_CHARS = 450
BULLET_TOLERANCE = 1


def find_violations(master: MasterCv, tailored: TailoredContent, max_projects: int) -> list[str]:
    return [
        *_check_summary(master, tailored),
        *_check_skills(master, tailored),
        *_check_entries(
            "experience",
            {entry.id: entry for entry in master.experience},
            tailored.experience,
            require_all=True,
        ),
        *_check_entries(
            "project",
            {entry.id: entry for entry in master.projects},
            tailored.projects,
            require_all=False,
        ),
        *_check_project_count(tailored, max_projects),
    ]


def _check_summary(master: MasterCv, tailored: TailoredContent) -> list[str]:
    violations: list[str] = []
    summary = tailored.summary.strip()
    if not summary:
        violations.append("summary is empty")
    if len(summary) > MAX_SUMMARY_CHARS:
        violations.append(f"summary has {len(summary)} characters, limit is {MAX_SUMMARY_CHARS}")
    allowed_numbers = _numeric_tokens(_flatten(master.model_dump()))
    violations.extend(
        f"summary contains number '{token}' that is not in the master CV"
        for token in sorted(_numeric_tokens([summary]) - allowed_numbers)
    )
    return violations


def _check_skills(master: MasterCv, tailored: TailoredContent) -> list[str]:
    master_groups = {normalize(group.group) for group in master.skills}
    master_items = {normalize(item) for group in master.skills for item in group.items}
    violations: list[str] = []
    for group in tailored.skills:
        if normalize(group.group) not in master_groups:
            violations.append(f"skill group '{group.group}' is not in the master CV")
        violations.extend(
            f"skill '{item}' is not in the master skill list"
            for item in group.items
            if normalize(item) not in master_items
        )
    return violations


def _check_entries(
    kind: str,
    master_entries: Mapping[str, Entry],
    tailored_entries: Sequence[TailoredEntry],
    require_all: bool,
) -> list[str]:
    counts = Counter(entry.id for entry in tailored_entries)
    violations = [f"unknown {kind} id '{i}'" for i in counts if i not in master_entries]
    violations.extend(f"duplicate {kind} id '{i}'" for i, count in counts.items() if count > 1)
    if require_all:
        violations.extend(f"missing {kind} id '{i}'" for i in master_entries if i not in counts)
    for entry in tailored_entries:
        master_entry = master_entries.get(entry.id)
        if master_entry is not None:
            violations.extend(_check_bullets(f"{kind} '{entry.id}'", master_entry, entry))
    return violations


def _check_bullets(label: str, master_entry: Entry, tailored_entry: TailoredEntry) -> list[str]:
    violations: list[str] = []
    master_count = len(master_entry.bullets)
    lowest = max(1, master_count - BULLET_TOLERANCE)
    highest = master_count + BULLET_TOLERANCE
    count = len(tailored_entry.bullets)
    if not lowest <= count <= highest:
        violations.append(f"{label} has {count} bullets, allowed range is {lowest}-{highest}")
    if any(not bullet.strip() for bullet in tailored_entry.bullets):
        violations.append(f"{label} has an empty bullet")
    allowed_numbers = _numeric_tokens(_flatten(master_entry.model_dump()))
    new_numbers = _numeric_tokens(tailored_entry.bullets) - allowed_numbers
    violations.extend(
        f"{label} contains number '{token}' that is not in its master text"
        for token in sorted(new_numbers)
    )
    return violations


def _check_project_count(tailored: TailoredContent, max_projects: int) -> list[str]:
    if len(tailored.projects) > max_projects:
        return [f"{len(tailored.projects)} projects selected, limit is {max_projects}"]
    return []


def _numeric_tokens(texts: Iterable[str]) -> set[str]:
    return {token for text in texts for token in NUMERIC_TOKEN.findall(text)}


def _flatten(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if key != "id":
                yield from _flatten(item)
    elif isinstance(value, Iterable):
        for item in value:
            yield from _flatten(item)
