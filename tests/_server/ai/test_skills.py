# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from marimo._server.ai.skills import (
    Skill,
    discover_skills,
    render_skills_for_system_prompt,
)

if TYPE_CHECKING:
    import pytest

    from marimo._config.config import SkillsConfig


def _write_skill(
    base: Path, folder: str, *, frontmatter: str | None, body: str
) -> Path:
    skill_dir = base / folder
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    parts: list[str] = []
    if frontmatter is not None:
        parts.append("---")
        parts.append(frontmatter.strip())
        parts.append("---")
        parts.append("")
    parts.append(body)
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def _isolate_defaults(monkeypatch: pytest.MonkeyPatch, sandbox: Path) -> None:
    # Point the "global" default paths at the sandbox so HOME-based
    # directories don't leak into unrelated developer machines.
    monkeypatch.setattr(
        "marimo._server.ai.skills.GLOBAL_SKILLS_DIR",
        sandbox / "global-home" / ".marimo" / "skills",
    )
    monkeypatch.setattr(
        "marimo._server.ai.skills.AGENTS_GLOBAL_SKILLS_DIR",
        sandbox / "global-home" / ".agents" / "skills",
    )


class TestDiscovery:
    def test_empty_when_nothing_on_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        result = discover_skills(None, cwd=tmp_path)
        assert result.skills == []
        assert any(p.name == "skills" for p in result.scanned_paths)
        assert result.warnings == []

    def test_discovers_project_skills(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "review",
            frontmatter=("name: review\ndescription: Review code for bugs"),
            body="# Review\n\nFlag bugs and perf problems.",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert [s.name for s in result.skills] == ["review"]
        assert result.skills[0].description == "Review code for bugs"
        assert result.skills[0].origin == "project"
        assert "Flag bugs" in result.skills[0].body

    def test_project_overrides_global_by_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        monkeypatch.setattr(
            "marimo._server.ai.skills.GLOBAL_SKILLS_DIR",
            home / ".marimo" / "skills",
        )
        monkeypatch.setattr(
            "marimo._server.ai.skills.AGENTS_GLOBAL_SKILLS_DIR",
            home / ".agents" / "skills",
        )
        _write_skill(
            home / ".marimo" / "skills",
            "shared",
            frontmatter="name: shared\ndescription: global version",
            body="global body",
        )
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "shared",
            frontmatter="name: shared\ndescription: project version",
            body="project body",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert len(result.skills) == 1
        assert result.skills[0].description == "project version"
        assert result.skills[0].origin == "project"

    def test_agents_interop_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        # Skills authored for Claude Code / pi in ``.agents/skills``
        # should be picked up unchanged.
        _write_skill(
            tmp_path / ".agents" / "skills",
            "interop",
            frontmatter="name: interop\ndescription: cross-agent skill",
            body="shared body",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert [s.name for s in result.skills] == ["interop"]
        assert result.skills[0].origin == "agents-project"

    def test_custom_paths_override_defaults(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        extra = tmp_path / "vendor"
        _write_skill(
            extra,
            "review",
            frontmatter="name: review\ndescription: vendor",
            body="vendor body",
        )
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "review",
            frontmatter="name: review\ndescription: project",
            body="project body",
        )
        config: SkillsConfig = {"custom_paths": [str(extra)]}
        result = discover_skills(config, cwd=tmp_path)
        # Custom paths are applied after defaults and therefore win.
        assert result.skills[0].description == "vendor"
        assert result.skills[0].origin == "custom"

    def test_include_default_paths_false_excludes_home_and_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "in-project",
            frontmatter="name: in-project\ndescription: ignore",
            body="ignored",
        )
        extra = tmp_path / "vendor"
        _write_skill(
            extra,
            "only-this",
            frontmatter="name: only-this\ndescription: keep",
            body="kept",
        )
        config: SkillsConfig = {
            "custom_paths": [str(extra)],
            "include_default_paths": False,
        }
        result = discover_skills(config, cwd=tmp_path)
        assert [s.name for s in result.skills] == ["only-this"]


class TestFrontmatter:
    def test_missing_frontmatter_defaults_to_directory_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "no-frontmatter",
            frontmatter=None,
            body="First paragraph is the description.\n\nSecond paragraph is body.",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert result.skills[0].name == "no-frontmatter"
        assert (
            result.skills[0].description
            == "First paragraph is the description."
        )

    def test_folded_description(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "folded",
            frontmatter=(
                "name: folded\n"
                "description: >-\n"
                "  This description spans\n"
                "  multiple lines and should\n"
                "  be folded into one."
            ),
            body="body",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert (
            result.skills[0].description
            == "This description spans multiple lines and should be folded into one."
        )

    def test_quoted_values_are_unquoted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "quoted",
            frontmatter='name: quoted\ndescription: "with colons: ok"',
            body="body",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert result.skills[0].description == "with colons: ok"

    def test_invalid_name_produces_warning_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "bad one",
            frontmatter="name: bad name with spaces",
            body="body",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert result.skills == []
        assert len(result.warnings) == 1
        assert "invalid skill name" in result.warnings[0]

    def test_directory_name_with_spaces_is_skipped_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        # When there's no frontmatter and the directory name isn't a
        # valid identifier, we emit a warning rather than registering the
        # skill.
        _write_skill(
            tmp_path / ".marimo" / "skills",
            "bad name",
            frontmatter=None,
            body="body",
        )
        result = discover_skills(None, cwd=tmp_path)
        assert result.skills == []
        assert any("invalid skill name" in w for w in result.warnings)


class TestRendering:
    def test_empty_list_renders_empty_string(self) -> None:
        assert render_skills_for_system_prompt([]) == ""

    def test_rendered_prompt_contains_body_and_description(self) -> None:
        skills = [
            Skill(
                name="viz",
                description="Use for visualizations",
                body="Prefer altair for statistical charts.",
                source=Path("/tmp/viz/SKILL.md"),
                origin="project",
            )
        ]
        rendered = render_skills_for_system_prompt(skills)
        assert "## Active skills" in rendered
        assert "### viz" in rendered
        assert "Use for visualizations" in rendered
        assert "Prefer altair" in rendered


class TestErrorHandling:
    def test_unreadable_directory_produces_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _isolate_defaults(monkeypatch, tmp_path)
        bad = tmp_path / "bad"
        bad.mkdir()
        # Simulate a permission error at iterdir time.
        with patch(
            "pathlib.Path.iterdir",
            side_effect=PermissionError("nope"),
        ):
            config: SkillsConfig = {
                "custom_paths": [str(bad)],
                "include_default_paths": False,
            }
            result = discover_skills(config, cwd=tmp_path)
        assert result.skills == []
        assert any("Could not list" in w for w in result.warnings)
