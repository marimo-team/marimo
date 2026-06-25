# Copyright 2026 Marimo. All rights reserved.

import functools
from pathlib import Path
from typing import Literal

SKILL_NAMES: list[str] = ["marimo-pair"]


@functools.lru_cache(maxsize=1)
def load_skill(skill_name: Literal["marimo-pair"]) -> str:
    """Read the bundled skill SKILL.md once and cache it."""
    return (Path(__file__).parent / skill_name / "SKILL.md").read_text(
        encoding="utf-8"
    )
