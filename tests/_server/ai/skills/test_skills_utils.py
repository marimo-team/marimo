# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._server.ai.skills.utils import SKILL_NAMES, load_skill


def test_load_skill_returns_skill_contents() -> None:
    content = load_skill("marimo-pair")
    assert content.strip()
    # The bundled skill carries its frontmatter name.
    assert "name: marimo-pair" in content


def test_load_skill_is_cached() -> None:
    # lru_cache returns the identical object on repeated calls.
    assert load_skill("marimo-pair") is load_skill("marimo-pair")


def test_all_declared_skills_are_loadable() -> None:
    for skill_name in SKILL_NAMES:
        assert load_skill(skill_name).strip()
