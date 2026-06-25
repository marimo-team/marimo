# Copyright 2026 Marimo. All rights reserved.

import functools
from pathlib import Path
from typing import Literal

SkillNameType = Literal["marimo-pair"]
SKILL_NAMES: list[SkillNameType] = ["marimo-pair"]

ReferenceNameType = Literal[
    "gotchas", "rich-representations", "notebook-improvements"
]
REFERENCE_NAMES: list[ReferenceNameType] = [
    "gotchas",
    "rich-representations",
    "notebook-improvements",
]


@functools.lru_cache(maxsize=1)
def load_skill(skill_name: SkillNameType) -> str:
    """Read the bundled skill SKILL.md once and cache it."""
    return (Path(__file__).parent / skill_name / "SKILL.md").read_text(
        encoding="utf-8"
    )


@functools.lru_cache(maxsize=3)
def load_reference(reference_name: ReferenceNameType) -> str:
    """Read the bundled reference file once and cache it."""
    return (
        Path(__file__).parent
        / "marimo-pair"
        / "references"
        / f"{reference_name}.md"
    ).read_text(encoding="utf-8")
