# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.env import env_to_value

_KEY = "MARIMO_TEST_ENV_TO_VALUE"


def test_unset_variable_returns_none(monkeypatch) -> None:
    monkeypatch.delenv(_KEY, raising=False)
    assert env_to_value(_KEY) is None


def test_boolean_values_are_parsed(monkeypatch) -> None:
    monkeypatch.setenv(_KEY, "true")
    assert env_to_value(_KEY) == (True,)
    monkeypatch.setenv(_KEY, "FALSE")
    assert env_to_value(_KEY) == (False,)


def test_list_values_are_split(monkeypatch) -> None:
    monkeypatch.setenv(_KEY, "[a,b,c]")
    assert env_to_value(_KEY) == (["a", "b", "c"],)


def test_none_string_returns_none(monkeypatch) -> None:
    # The literal string "none" maps back to None (not a wrapped value).
    monkeypatch.setenv(_KEY, "none")
    assert env_to_value(_KEY) is None


def test_plain_string_is_wrapped(monkeypatch) -> None:
    monkeypatch.setenv(_KEY, "hello")
    assert env_to_value(_KEY) == ("hello",)
