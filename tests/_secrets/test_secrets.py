from __future__ import annotations

import os
from typing import TYPE_CHECKING

from marimo._config.config import MarimoConfig
from marimo._secrets.secrets import get_secret_keys

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_get_secret_keys_basic(monkeypatch: pytest.MonkeyPatch):
    # Setup environment variables
    monkeypatch.setenv("ENV_SECRET", "value")
    original_environ = os.environ.copy()

    config = MarimoConfig(
        runtime={
            "dotenv": [],
        }
    )

    result = get_secret_keys(config, original_environ)

    # Should have one provider (env)
    assert len(result) == 1
    assert result[0].provider == "env"
    assert "ENV_SECRET" in result[0].keys


def test_get_secret_keys_empty(monkeypatch: pytest.MonkeyPatch):
    # Clear any test environment variables
    config = MarimoConfig(
        runtime={
            "dotenv": [],
        }
    )

    # Add a test key
    test_key = "TEST_SECRET_KEY_UNIQUE"
    monkeypatch.setenv(test_key, "value")
    original_environ = os.environ.copy()

    result = get_secret_keys(config, original_environ)

    # Should have one provider (env)
    assert len(result) == 1
    assert result[0].provider == "env"

    # Our test key should be in the result
    assert test_key in result[0].keys


def test_get_secret_keys_with_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Create a .env file
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DOTENV_SECRET=secret_value\nSHARED_SECRET=dotenv_value"
    )

    # Set an environment variable that will override the .env file
    monkeypatch.setenv("SHARED_SECRET", "env_value")
    original_environ = os.environ.copy()

    config = MarimoConfig(
        runtime={
            "dotenv": [str(env_file)],
        }
    )

    result = get_secret_keys(config, original_environ)

    # Should have two providers (env and dotenv)
    assert len(result) == 2

    # First provider should be env
    assert result[0].provider == "env"
    assert "SHARED_SECRET" in result[0].keys

    # Second provider should be dotenv
    assert result[1].provider == "dotenv"
    assert "DOTENV_SECRET" in result[1].keys
    # SHARED_SECRET should not be in dotenv keys since it's already in env
    assert "SHARED_SECRET" not in result[1].keys


def test_get_secret_keys_multiple_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Create two .env files
    env_file1 = tmp_path / ".env1"
    env_file1.write_text("DOTENV1_SECRET=value1\nSHARED_SECRET=dotenv1_value")

    env_file2 = tmp_path / ".env2"
    env_file2.write_text("DOTENV2_SECRET=value2\nSHARED_SECRET=dotenv2_value")

    # Set an environment variable
    monkeypatch.setenv("ENV_SECRET", "env_value")
    original_environ = os.environ.copy()

    config = MarimoConfig(
        runtime={
            "dotenv": [str(env_file1), str(env_file2)],
        }
    )

    result = get_secret_keys(config, original_environ)

    # Should have three providers (env and two dotenv)
    assert len(result) == 3

    # First provider should be env
    assert result[0].provider == "env"
    assert "ENV_SECRET" in result[0].keys

    # Second provider should be first dotenv
    assert result[1].provider == "dotenv"
    assert "DOTENV1_SECRET" in result[1].keys
    assert "SHARED_SECRET" in result[1].keys

    # Third provider should be second dotenv
    assert result[2].provider == "dotenv"
    assert "DOTENV2_SECRET" in result[2].keys
    # SHARED_SECRET should not be in second dotenv keys since it's already in first dotenv
    assert "SHARED_SECRET" not in result[2].keys
