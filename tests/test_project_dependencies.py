from __future__ import annotations

import pytest

from tests.mocks import snapshotter

snapshot = snapshotter(__file__)


def test_required_dependencies(pyproject_text: str) -> None:
    import tomlkit

    pyproject = tomlkit.loads(pyproject_text)
    deps = sorted(pyproject["project"]["dependencies"])
    snapshot("dependencies.txt", "\n".join(deps), keep_version=True)


@pytest.mark.parametrize(
    "extra",
    ["sql", "sandbox", "recommended", "lsp", "mcp"],
)
def test_optional_dependencies(extra: str, pyproject_text: str) -> None:
    import tomlkit

    pyproject = tomlkit.loads(pyproject_text)
    deps = sorted(pyproject["project"]["optional-dependencies"][extra])
    snapshot(
        f"optional-dependencies-{extra}.txt",
        "\n".join(deps),
        keep_version=True,
    )
