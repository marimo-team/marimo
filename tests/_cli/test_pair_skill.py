# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
SKILL_PATH = ROOT / "skills" / "marimo-pair" / "SKILL.md"


def test_root_skill_is_a_thin_model_invoked_bootstrap() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter, body = text.removeprefix("---\n").split("---\n", 1)
    metadata = yaml.safe_load(frontmatter)

    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == "marimo-pair"
    assert metadata["description"].startswith("Use when ")
    assert "running marimo notebook" in metadata["description"]
    assert len(text.splitlines()) < 40
    assert "uvx marimo@latest pair guide" in body
    assert "context compaction" in body


def test_root_skill_omits_versioned_transport_details() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8").lower()

    for transport_detail in (
        "/api/",
        "registry",
        "code mode",
        ".sh",
        "curl",
        "jq",
    ):
        assert transport_detail not in text


def test_wheel_contains_all_pair_guide_resources() -> None:
    dist = ROOT / ".context" / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = max(
        dist.glob("marimo-*.whl"), key=lambda path: path.stat().st_mtime
    )

    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())

    assert {
        "marimo/_server/ai/skills/marimo-pair/SKILL.md",
        "marimo/_server/ai/skills/marimo-pair/adapters/cli.md",
        "marimo/_server/ai/skills/marimo-pair/adapters/code-mode.md",
        "marimo/_server/ai/skills/marimo-pair/references/gotchas.md",
        "marimo/_server/ai/skills/marimo-pair/references/notebook-improvements.md",
        "marimo/_server/ai/skills/marimo-pair/references/rich-representations.md",
    } <= members
