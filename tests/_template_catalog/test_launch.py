# Copyright 2026 Marimo. All rights reserved.

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from marimo._template_catalog import (
    TemplateLaunchNotFoundError,
    TemplateManager,
    TemplateNotFoundError,
)


def test_create_and_resolve_launch() -> None:
    manager = TemplateManager()

    key = manager.create_launch("interactive-controls")
    source = manager.resolve_launch(key)

    assert source is not None
    assert 'label="Number of stars"' in source
    assert manager.resolve_launch(key) == source


def test_unknown_template_cannot_launch() -> None:
    manager = TemplateManager()

    with pytest.raises(TemplateNotFoundError):
        manager.create_launch("missing")


def test_invalid_and_consumed_launches_are_rejected() -> None:
    manager = TemplateManager()
    key = manager.create_launch("interactive-controls")

    manager.consume_launch(key)

    with pytest.raises(TemplateLaunchNotFoundError):
        manager.resolve_launch(key)
    with pytest.raises(TemplateLaunchNotFoundError):
        manager.resolve_launch("__marimo_template__missing")
    assert manager.resolve_launch("not-a-template-key") is None


def test_launch_expires() -> None:
    now = [10.0]
    manager = TemplateManager(
        launch_ttl_seconds=5,
        clock=lambda: now[0],
    )
    key = manager.create_launch("interactive-controls")

    now[0] = 15.0

    with pytest.raises(TemplateLaunchNotFoundError):
        manager.resolve_launch(key)


def test_launch_count_is_bounded() -> None:
    tokens = iter(["one", "two", "three"])
    manager = TemplateManager(
        max_launches=2,
        token_factory=lambda: next(tokens),
    )
    first = manager.create_launch("interactive-controls")
    second = manager.create_launch("interactive-controls")
    third = manager.create_launch("interactive-controls")

    with pytest.raises(TemplateLaunchNotFoundError):
        manager.resolve_launch(first)
    assert manager.resolve_launch(second) is not None
    assert manager.resolve_launch(third) is not None


def test_concurrent_launches_are_independent() -> None:
    manager = TemplateManager(max_launches=20)

    with ThreadPoolExecutor(max_workers=8) as executor:
        keys = list(
            executor.map(
                manager.create_launch,
                ["interactive-controls"] * 20,
            )
        )

    assert len(set(keys)) == 20
    assert len({manager.resolve_launch(key) for key in keys}) == 1
