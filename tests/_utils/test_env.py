# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.env import is_env_true

KEY = "MARIMO_TEST_IS_ENV_TRUE"


def test_is_env_true_unset_uses_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(KEY, raising=False)
    assert is_env_true(KEY) is False
    assert is_env_true(KEY, default=True) is True


@pytest.mark.parametrize(
    "value",
    ["true", "1", "TRUE", "True", " true ", "\t1\n"],
)
def test_is_env_true_truthy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(KEY, value)
    assert is_env_true(KEY) is True
    # An explicit truthy value overrides a True default too.
    assert is_env_true(KEY, default=False) is True


@pytest.mark.parametrize(
    "value",
    ["false", "0", "no", "yes", "", "2", "on", "off"],
)
def test_is_env_true_falsy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(KEY, value)
    assert is_env_true(KEY) is False
    # A set-but-falsy value overrides a True default.
    assert is_env_true(KEY, default=True) is False
