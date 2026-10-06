from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from packages import pytest_changed

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any


def test_get_dependency_graph_uses_project_ruff_version(
    monkeypatch: Any, tmp_path: Path
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)

    assert pytest_changed.get_dependency_graph(tmp_path) == {}
    assert calls == [
        (
            [
                "uvx",
                "--exclude-newer-package",
                "ruff=false",
                "ruff@0.16.10",
                "analyze",
                "graph",
                "--detect-string-imports",
                "--direction",
                "dependents",
                ".",
            ],
            {
                "cwd": tmp_path,
                "capture_output": True,
                "text": True,
                "check": True,
            },
        )
    ]
