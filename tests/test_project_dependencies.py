from __future__ import annotations

from pathlib import Path

import pytest

from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def _load_pyproject():
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)


def test_required_dependencies():
    pyproject = _load_pyproject()
    deps = sorted(pyproject["project"]["dependencies"])
    snapshot("dependencies.txt", "\n".join(deps))


@pytest.mark.parametrize(
    "extra",
    ["sql", "sandbox", "recommended", "lsp", "mcp"],
)
def test_optional_dependencies(extra: str):
    pyproject = _load_pyproject()
    deps = sorted(pyproject["project"]["optional-dependencies"][extra])
    snapshot(f"optional-dependencies-{extra}.txt", "\n".join(deps))
