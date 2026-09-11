# Copyright 2026 Marimo. All rights reserved.
"""Shared fixtures for tests that invoke a real environment manager."""

from __future__ import annotations

import pytest

# Ambient configuration that changes which versions a manager resolves.
# These tests assert marimo's own behavior, so a shell or CI job that sets
# one of these (the minimal-dependency job sets `UV_RESOLUTION`) must not
# change what they resolve.
RESOLUTION_VARIABLES = ("UV_RESOLUTION", "UV_PRERELEASE")


@pytest.fixture(autouse=True)
def ignore_ambient_resolution_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in RESOLUTION_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
