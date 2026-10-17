import ast
import io
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = sorted(path for folder in ("src", "tests") for path in (ROOT / folder).rglob("*.py"))


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda path: str(path.relative_to(ROOT)))
def test_file_has_no_comments(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    assert [token.string for token in tokens if token.type == tokenize.COMMENT] == []


@pytest.mark.parametrize("path", PYTHON_FILES, ids=lambda path: str(path.relative_to(ROOT)))
def test_file_has_no_docstrings(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    documented = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and ast.get_docstring(node, clean=False) is not None
    ]
    assert documented == []


def test_python_files_were_discovered() -> None:
    assert PYTHON_FILES
