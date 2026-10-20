import re

UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
FALLBACK_FILENAME = "Resume.pdf"
FILENAME_SUFFIX = "Resume"


def build_filename(contact_name: str) -> str:
    words = [word for word in map(_sanitize_part, contact_name.split()) if word]
    if not words:
        return FALLBACK_FILENAME
    name_parts = words if len(words) == 1 else [words[0], words[-1]]
    return "_".join([*name_parts, FILENAME_SUFFIX]) + ".pdf"


def _sanitize_part(text: str) -> str:
    return UNSAFE_FILENAME_CHARS.sub("_", text).strip("_.")
