# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.env import env_to_value, is_env_true

KEY = "MARIMO_TEST_IS_ENV_TRUE"
ENV_TO_VALUE_KEY = "MARIMO_TEST_ENV_TO_VALUE"


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


def test_env_to_value_unset_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_TO_VALUE_KEY, raising=False)
    assert env_to_value(ENV_TO_VALUE_KEY) is None


def test_env_to_value_parses_booleans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_TO_VALUE_KEY, "true")
    assert env_to_value(ENV_TO_VALUE_KEY) == (True,)
    monkeypatch.setenv(ENV_TO_VALUE_KEY, "FALSE")
    assert env_to_value(ENV_TO_VALUE_KEY) == (False,)


def test_env_to_value_splits_lists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_TO_VALUE_KEY, "[a,b,c]")
    assert env_to_value(ENV_TO_VALUE_KEY) == (["a", "b", "c"],)


def test_env_to_value_none_string_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The literal string "none" maps back to None (not a wrapped value).
    monkeypatch.setenv(ENV_TO_VALUE_KEY, "none")
    assert env_to_value(ENV_TO_VALUE_KEY) is None


def test_env_to_value_wraps_plain_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_TO_VALUE_KEY, "hello")
    assert env_to_value(ENV_TO_VALUE_KEY) == ("hello",)
