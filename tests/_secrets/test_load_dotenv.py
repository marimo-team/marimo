from __future__ import annotations

import os
from typing import TYPE_CHECKING

from marimo._secrets.load_dotenv import (
    _drop_quotes,
    load_dotenv_with_fallback,
    load_to_environ,
    parse_dotenv,
    read_dotenv_with_fallback,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_drop_quotes():
    assert _drop_quotes('"value"') == "value"
    assert _drop_quotes("'value'") == "value"
    assert _drop_quotes("value") == "value"
    assert _drop_quotes('"value') == '"value'
    assert _drop_quotes("value'") == "value'"


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
