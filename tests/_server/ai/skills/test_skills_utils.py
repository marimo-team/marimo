# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._server.ai.skills.utils import (
    REFERENCE_NAMES,
    SKILL_NAMES,
    load_reference,
    load_skill,
)


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


def test_load_reference_returns_reference_contents() -> None:
    content = load_reference("gotchas")
    assert content.strip()
    assert content.startswith("# Gotchas")


def test_load_reference_is_cached() -> None:
    assert load_reference("gotchas") is load_reference("gotchas")


def test_all_declared_references_are_loadable() -> None:
    for reference_name in REFERENCE_NAMES:
        assert load_reference(reference_name).strip()


def test_reference_files_point_to_load_capability() -> None:
    for reference_name in REFERENCE_NAMES:
        content = load_reference(reference_name)
        assert "load_capability" in content
        assert f"`{reference_name}` capability" in content
        assert "Loaded on demand via" in content
