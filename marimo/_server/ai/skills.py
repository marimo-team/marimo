# Copyright 2026 Marimo. All rights reserved.
"""On-disk AI skills auto-loaded into marimo's AI system prompts.

Skills are folders with a ``SKILL.md`` file — the same format Claude Code
and pi use (see https://agentskills.io). marimo discovers them at request
time and appends their bodies to the system prompt of every chat and
refactor call, so the model has access to user-authored guidance without
any in-editor action.

Example ``SKILL.md``::

    ---
    name: marimo-viz
    description: >-
        Use when the user asks for visualizations, charts, or plots. Prefer
        altair for statistical charts; return chart objects as the last
        expression.
    ---

    # Visualization skill

    - Use ``alt.Chart(df)`` directly on polars/pandas dataframes.
    - Return the chart object as the last expression of the cell.
    - ...

Default search paths (later entries override earlier ones by ``name``):

1. ``~/.marimo/skills/`` — origin ``"global"``
2. ``~/.agents/skills/`` — origin ``"agents-global"`` (cross-agent interop)
3. ``<cwd>/.marimo/skills/`` — origin ``"project"``
4. ``<cwd>/.agents/skills/`` — origin ``"agents-project"``
5. Any ``custom_paths`` from ``[ai.skills]`` — origin ``"custom"``

A ``custom_paths`` entry may point at either a directory containing
``<name>/SKILL.md`` subfolders (standard layout) or a specific ``SKILL.md``
file.

Frontmatter is a small ``key: value`` subset of YAML (``name``,
``description``); we deliberately avoid a YAML dependency for a surface
this small. Richer frontmatter can be added incrementally.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from marimo import _loggers

if TYPE_CHECKING:
    from collections.abc import Iterable

    from marimo._config.config import SkillsConfig

LOGGER = _loggers.marimo_logger()

SkillOrigin = Literal[
    "global", "project", "agents-global", "agents-project", "custom"
]

GLOBAL_SKILLS_DIR = Path("~/.marimo/skills").expanduser()
AGENTS_GLOBAL_SKILLS_DIR = Path("~/.agents/skills").expanduser()
PROJECT_SKILLS_DIRNAME = ".marimo/skills"
AGENTS_PROJECT_SKILLS_DIRNAME = ".agents/skills"

SKILL_FILENAME = "SKILL.md"

# Skill names must be URL- and slash-safe so we can expose ``/skill:<name>``
# commands in a follow-up without breaking changes.
_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# Leading ``---``-fenced frontmatter block.
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)

# Header printed once before any skills are listed in the system prompt.
_SKILLS_PREAMBLE = (
    "The user has the following skills installed. Apply them when the "
    "described situation arises; they represent explicit user preferences "
    "and override generic defaults."
)


@dataclass(frozen=True)
class Skill:
    """A discovered skill, ready for API surfacing or prompt injection."""

    name: str
    description: str
    body: str
    source: Path
    origin: SkillOrigin

    @property
    def approx_tokens(self) -> int:
        # A generous whitespace-split is close enough for a UI hint; we're
        # not computing billing, just "is this skill heavy?".
        return len((self.description + "\n" + self.body).split())


@dataclass(frozen=True)
class DiscoveryResult:
    skills: list[Skill]
    scanned_paths: list[Path]
    warnings: list[str]


def discover_skills(
    config: SkillsConfig | None,
    *,
    cwd: Path | None = None,
) -> DiscoveryResult:
    """Discover on-disk skills from the configured paths.

    Project paths override global paths; ``.agents`` paths sit between
    ``.marimo`` paths of the same scope, so a marimo-specific skill always
    wins over a cross-agent one with the same name. ``custom_paths`` are
    applied last and override everything else.
    """
    cwd = cwd or Path.cwd()
    include_defaults = True
    custom_paths: list[str] = []
    if config is not None:
        include_defaults = config.get("include_default_paths", True)
        custom_paths = list(config.get("custom_paths", []) or [])

    sources: list[tuple[Path, SkillOrigin]] = []
    if include_defaults:
        sources.extend(
            [
                (GLOBAL_SKILLS_DIR, "global"),
                (AGENTS_GLOBAL_SKILLS_DIR, "agents-global"),
                (cwd / PROJECT_SKILLS_DIRNAME, "project"),
                (cwd / AGENTS_PROJECT_SKILLS_DIRNAME, "agents-project"),
            ]
        )
    for raw in custom_paths:
        sources.append((_resolve_path(raw, cwd), "custom"))

    by_name: dict[str, Skill] = {}
    scanned: list[Path] = []
    warnings: list[str] = []
    for path, origin in sources:
        scanned.append(path)
        for skill, warning in _load_source(path, origin):
            if warning is not None:
                warnings.append(warning)
            if skill is not None:
                by_name[skill.name] = skill

    skills = sorted(by_name.values(), key=lambda s: s.name)
    return DiscoveryResult(
        skills=skills, scanned_paths=scanned, warnings=warnings
    )


def render_skills_for_system_prompt(skills: list[Skill]) -> str:
    """Format a list of skills for appending to a system prompt.

    Returns an empty string when there are no skills, so callers can
    unconditionally concatenate the result without branching.
    """
    if not skills:
        return ""
    parts: list[str] = ["", "## Active skills", "", _SKILLS_PREAMBLE, ""]
    for skill in skills:
        parts.append(f"### {skill.name}")
        if skill.description:
            parts.append(f"_{skill.description}_")
            parts.append("")
        parts.append(skill.body.strip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _resolve_path(raw: str, cwd: Path) -> Path:
    expanded = os.path.expanduser(raw)
    path = Path(expanded)
    return path if path.is_absolute() else (cwd / path)


def _load_source(
    path: Path, origin: SkillOrigin
) -> Iterable[tuple[Skill | None, str | None]]:
    """Load skills from either a directory of skill folders or a single SKILL.md."""
    try:
        exists = path.exists()
    except OSError as exc:
        yield None, f"Could not stat {path}: {exc}"
        return
    if not exists:
        return

    if path.is_file():
        # A ``custom_paths`` entry pointing straight at a SKILL.md.
        yield _load_file(path, path.parent.name or path.stem, origin)
        return

    try:
        entries = sorted(p for p in path.iterdir() if p.is_dir())
    except OSError as exc:
        yield None, f"Could not list {path}: {exc}"
        return

    for entry in entries:
        skill_file = entry / SKILL_FILENAME
        if not skill_file.is_file():
            continue
        yield _load_file(skill_file, entry.name, origin)


def _load_file(
    path: Path, default_name: str, origin: SkillOrigin
) -> tuple[Skill | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Could not read {path}: {exc}"

    frontmatter, body = _split_frontmatter(raw)
    name = frontmatter.get("name", default_name).strip()
    if not _NAME_PATTERN.match(name):
        return None, (
            f"Skipping {path}: invalid skill name {name!r} "
            "(must match [A-Za-z0-9_-]+)"
        )

    description = frontmatter.get("description", "").strip()
    if not description:
        description = _first_paragraph(body)

    return (
        Skill(
            name=name,
            description=description,
            body=body.strip(),
            source=path,
            origin=origin,
        ),
        None,
    )


def _split_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        return {}, raw
    return _parse_frontmatter(match.group("body")), raw[match.end() :]


def _parse_frontmatter(block: str) -> dict[str, str]:
    """Parse a tiny ``key: value`` subset of YAML.

    Enough for ``name``/``description``. Supports single-line folded values
    introduced with ``>-`` (consumed from the following indented lines).
    Everything more exotic (nested mappings, lists, anchors) is out of
    scope on purpose — we want to stay stdlib-only here.
    """
    result: dict[str, str] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        key, sep, value = line.partition(":")
        if not sep:
            i += 1
            continue
        key = key.strip()
        value = value.strip()
        if value == ">-" or value == ">":
            folded: list[str] = []
            j = i + 1
            while j < len(lines) and (
                lines[j].startswith((" ", "\t")) or not lines[j].strip()
            ):
                folded.append(lines[j].strip())
                j += 1
            value = " ".join(chunk for chunk in folded if chunk)
            i = j
        else:
            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in ("'", '"')
            ):
                value = value[1:-1]
            i += 1
        if key:
            result[key] = value
    return result


def _first_paragraph(body: str) -> str:
    for chunk in body.strip().split("\n\n"):
        cleaned = chunk.strip()
        if cleaned:
            return " ".join(cleaned.split())
    return ""
