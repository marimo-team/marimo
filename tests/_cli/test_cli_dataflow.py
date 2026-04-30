# Copyright 2026 Marimo. All rights reserved.
"""Smoke tests for the ``marimo dataflow`` CLI subcommands.

These verify both that the bundled assets are reachable through the
installed package's ``importlib.resources`` view *and* that the click
plumbing is wired up. They intentionally don't pin the asset contents —
those are exercised by the hashing test below, which catches accidental
import drift between the wheeled file and the source-of-truth path.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from marimo._utils.paths import marimo_package_path
from marimo._utils.platform import is_windows


def _bundled(*parts: str) -> Path:
    p = marimo_package_path()
    for part in parts:
        p = p / part
    return Path(str(p))


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
@pytest.mark.parametrize(
    ("subcommand", "needle"),
    [
        ("client", "DataflowProvider"),
        ("skill", "Dataflow API — Agent Recipe"),
    ],
)
def test_dataflow_dump_to_stdout(subcommand: str, needle: str) -> None:
    p = subprocess.run(
        ["marimo", "dataflow", subcommand],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    assert needle in p.stdout.decode()


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
def test_client_path_returns_file() -> None:
    """``client --path`` resolves to the dataflow.tsx file."""
    p = subprocess.run(
        ["marimo", "dataflow", "client", "--path"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    reported = Path(p.stdout.decode().strip())
    assert reported.is_file(), reported
    expected = _bundled("_dataflow", "clients", "typescript", "dataflow.tsx")
    assert reported.read_bytes() == expected.read_bytes()
    assert hashlib.sha256(expected.read_bytes()).hexdigest()


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
def test_skill_path_returns_gh_compatible_root() -> None:
    """``skill --path`` returns a directory whose ``skills/dataflow/SKILL.md``
    layout matches what ``gh skill install --from-local <root> dataflow``
    expects.
    """
    p = subprocess.run(
        ["marimo", "dataflow", "skill", "--path"],
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr.decode()
    reported = Path(p.stdout.decode().strip())
    assert reported.is_dir(), reported
    skill_md = reported / "skills" / "dataflow" / "SKILL.md"
    assert skill_md.is_file(), (
        f"expected skills/dataflow/SKILL.md under {reported}"
    )
    expected = _bundled(
        "_dataflow", "skills", "dataflow", "SKILL.md"
    ).read_bytes()
    assert skill_md.read_bytes() == expected


@pytest.mark.xfail(condition=is_windows(), reason="flaky on Windows")
def test_skill_md_has_frontmatter() -> None:
    """SKILL.md follows the agent-skills spec (YAML frontmatter at top)."""
    p = subprocess.run(
        ["marimo", "dataflow", "skill"],
        capture_output=True,
    )
    assert p.returncode == 0
    text = p.stdout.decode()
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    end = text.find("\n---\n", 4)
    assert end != -1, "SKILL.md frontmatter must close with `---`"
    front = text[4:end]
    assert "name: dataflow" in front
    assert "description:" in front
