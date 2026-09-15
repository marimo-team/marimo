from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._secrets.load_dotenv import (
    _drop_quotes,
    escape_dotenv_value,
    load_dotenv_with_fallback,
    load_to_environ,
    parse_dotenv,
    read_dotenv_with_fallback,
    resolve_dotenv_value,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_drop_quotes():
    assert _drop_quotes('"value"') == "value"
    assert _drop_quotes("'value'") == "value"
    assert _drop_quotes("value") == "value"
    assert _drop_quotes('"value') == '"value'
    assert _drop_quotes("value'") == "value'"
    assert _drop_quotes('"') == '"'
    assert _drop_quotes("'") == "'"


def test_drop_quotes_unescapes_double_quoted_values():
    # Escape sequences are only decoded inside double quotes, matching
    # python-dotenv.
    assert _drop_quotes(r'"{\"type\": \"service_account\"}"') == (
        '{"type": "service_account"}'
    )
    assert _drop_quotes(r'"C:\\tmp"') == "C:\\tmp"
    assert _drop_quotes(r'"line1\nline2"') == "line1\nline2"
    # A literal backslash-n is written as `\\n`, and stays a literal.
    assert _drop_quotes(r'"a\\nb"') == r"a\nb"
    # Unknown escapes are left alone.
    assert _drop_quotes(r'"50\% off"') == r"50\% off"
    assert _drop_quotes(r"'{\"type\": 1}'") == r"{\"type\": 1}"


def test_parse_dotenv(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# Comment
KEY1=value1
KEY2="value2"
KEY3='value3'
KEY4=
KEY5="value5
KEY6=value6"
"""
    )

    env_dict = parse_dotenv(str(env_file))
    assert env_dict == {
        "KEY1": "value1",
        "KEY2": "value2",
        "KEY3": "value3",
        "KEY4": "",
        "KEY5": '"value5',
        "KEY6": 'value6"',
    }


def test_parse_dotenv_nonexistent():
    env_dict = parse_dotenv("nonexistent.env")
    assert env_dict == {}


def test_load_to_environ():
    env_dict = {"TEST_KEY": "test_value"}
    load_to_environ(env_dict)
    assert os.environ["TEST_KEY"] == "test_value"
    del os.environ["TEST_KEY"]


def test_load_dotenv_with_fallback(tmp_path: Path):
    # Should work regardless of whether dotenv is installed
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_KEY=test_value")

    load_dotenv_with_fallback(str(env_file))
    assert os.environ["TEST_KEY"] == "test_value"
    del os.environ["TEST_KEY"]


def test_read_dotenv_with_fallback(tmp_path: Path):
    # Should work regardless of whether dotenv is installed
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_KEY=test_value")

    env_dict = read_dotenv_with_fallback(str(env_file))
    assert env_dict == {"TEST_KEY": "test_value"}


def test_read_dotenv_interpolates_from_environment(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "FROM_ENV=${BASE}/env\nLOCAL=local\nFROM_FILE=${LOCAL}/file",
        encoding="utf-8",
    )

    env_dict = read_dotenv_with_fallback(
        str(env_file), environment={"BASE": "base"}
    )

    assert env_dict == {
        "FROM_ENV": "base/env",
        "LOCAL": "local",
        "FROM_FILE": "local/file",
    }


def test_read_dotenv_interpolates_duplicate_assignments_in_order(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "A=first\nB=${A}\nA=second\nC=${A}",
        encoding="utf-8",
    )

    env_dict = read_dotenv_with_fallback(str(env_file), environment={})

    assert env_dict == {
        "A": "second",
        "B": "first",
        "C": "second",
    }


def test_resolve_dotenv_value_preserves_precedence_and_interpolation(
    tmp_path: Path,
) -> None:
    first_env = tmp_path / ".env.first"
    first_env.write_text(
        "BASE=first\nENV_WINS=first",
        encoding="utf-8",
    )
    second_env = tmp_path / ".env.second"
    second_env.write_text(
        "BASE=second\nDERIVED=${BASE}/second\nENV_WINS=second",
        encoding="utf-8",
    )

    resolved = resolve_dotenv_value(
        "DERIVED",
        [str(first_env), str(second_env)],
        {"ENV_WINS": "environment"},
    )

    assert resolved == "first/second"


def test_resolve_dotenv_value_stops_after_environment_value(
    tmp_path: Path,
) -> None:
    unreadable = tmp_path / "not-a-file"
    unreadable.mkdir()

    resolved = resolve_dotenv_value(
        "API_KEY",
        [str(unreadable)],
        {"API_KEY": "environment"},
    )

    assert resolved == "environment"


def test_resolve_dotenv_value_stops_after_first_dotenv_value(
    tmp_path: Path,
) -> None:
    first_env = tmp_path / ".env.first"
    first_env.write_text("API_KEY=first", encoding="utf-8")
    unreadable = tmp_path / "not-a-file"
    unreadable.mkdir()

    resolved = resolve_dotenv_value(
        "API_KEY",
        [str(first_env), str(unreadable)],
        {},
    )

    assert resolved == "first"


ROUND_TRIP_VALUES = [
    "simple",
    'json {"type": "service_account", "id": 1}',
    r'{"private_key": "-----BEGIN-----\nabc\n-----END-----\n"}',
    "C:\\Users\\tmp",
    "multi\nline",
    "carriage\r\nreturn",
    "single 'quoted'",
    "tab\tseparated",
    "trailing backslash \\",
    "# not a comment",
]


@pytest.mark.parametrize("value", ROUND_TRIP_VALUES)
def test_write_key_round_trips(tmp_path: Path, value: str):
    from marimo._secrets.env_provider import DotEnvSecretsProvider

    env_file = tmp_path / ".env"
    env_file.touch()
    DotEnvSecretsProvider(str(env_file)).write_key("SECRET", value)

    # The fallback parser, which is what most installs use
    assert parse_dotenv(str(env_file))["SECRET"] == value
    # ...and python-dotenv, which must agree with it
    assert read_dotenv_with_fallback(str(env_file))["SECRET"] == value


@pytest.mark.skipif(
    not DependencyManager.dotenv.has(), reason="dotenv is not installed"
)
@pytest.mark.parametrize("value", ROUND_TRIP_VALUES)
def test_escape_dotenv_value_matches_dotenv(tmp_path: Path, value: str):
    from dotenv import dotenv_values

    env_file = tmp_path / ".env"
    env_file.write_text(
        f'SECRET="{escape_dotenv_value(value)}"\n', encoding="utf-8"
    )
    assert dotenv_values(str(env_file))["SECRET"] == value
    assert parse_dotenv(str(env_file))["SECRET"] == value


def test_load_dotenv_no_override(tmp_path: Path):
    # Test that existing environment variables are not overridden
    env_file = tmp_path / ".env"
    env_file.write_text("SOME_KEY=env_value")

    # Set the environment variable before loading
    os.environ["SOME_KEY"] = "env_value"

    env_file_2 = tmp_path / ".env2"
    env_file_2.write_text("SOME_KEY=a_new_value")

    # Load the .env file
    load_dotenv_with_fallback(str(env_file))

    # Verify the original value is preserved
    assert os.environ["SOME_KEY"] == "env_value"

    # Clean up
    del os.environ["SOME_KEY"]
