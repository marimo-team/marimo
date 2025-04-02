from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from marimo._config.config import MarimoConfig
from marimo._secrets.secrets import get_secret_keys, write_secret
from marimo._server.models.secrets import CreateSecretRequest

if TYPE_CHECKING:
    from pathlib import Path


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


def test_write_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Create a .env file
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_SECRET=value")

    # Set an environment variable
    monkeypatch.setenv("ENV_SECRET", "env_value")

    config = MarimoConfig(
        runtime={
            "dotenv": [str(env_file)],
        }
    )

    # Write a new secret to the dotenv file
    write_secret(
        CreateSecretRequest(
            key="NEW_SECRET",
            value="new_value",
            provider="dotenv",
            name=".env",
        ),
        config,
    )

    # Verify the secret was written to the file
    content = env_file.read_text()
    assert "EXISTING_SECRET=value" in content
    assert 'NEW_SECRET="new_value"' in content

    # Try to write to env provider (should raise an error)
    with pytest.raises(NotImplementedError):
        write_secret(
            CreateSecretRequest(
                key="ENV_SECRET",
                value="new_env_value",
                provider="env",
                name="Environment variables",
            ),
            config,
        )


def test_write_invalid_secret(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING_SECRET=value")

    config = MarimoConfig(
        runtime={
            "dotenv": [str(env_file)],
        }
    )

    # Empty key
    with pytest.raises(AssertionError):
        write_secret(
            CreateSecretRequest(
                key="",
                value="new_env_value",
                provider="dotenv",
                name=".env",
            ),
            config,
        )

    # Empty value
    with pytest.raises(AssertionError):
        write_secret(
            CreateSecretRequest(
                key="NEW_SECRET",
                value="",
                provider="dotenv",
                name=".env",
            ),
            config,
        )

    # Key with whitespace
    with pytest.raises(ValueError):
        write_secret(
            CreateSecretRequest(
                key="NEW SECRET",
                value="new_env_value",
                provider="dotenv",
                name=".env",
            ),
            config,
        )


def test_write_secret_multiple_dotenv(tmp_path: Path):
    # Create two .env files
    env_file1 = tmp_path / ".env1"
    env_file1.write_text("DOTENV1_SECRET=value1")

    env_file2 = tmp_path / ".env2"
    env_file2.write_text("DOTENV2_SECRET=value2")

    original_environ = os.environ.copy()

    config = MarimoConfig(
        runtime={
            "dotenv": [str(env_file1), str(env_file2)],
        }
    )

    # Write a new secret - should go to the first dotenv file by default
    write_secret(
        CreateSecretRequest(
            key="NEW_SECRET",
            value="new_value",
            provider="dotenv",
            name=".env1",
        ),
        config,
    )
    # Verify the secret was written to the first file
    content1 = env_file1.read_text()
    assert content1 == 'DOTENV1_SECRET=value1\nNEW_SECRET="new_value"\n'

    # Verify the second file is unchanged
    content2 = env_file2.read_text()
    assert "NEW_SECRET" not in content2


def test_write_secret_nonexistent_file(tmp_path: Path):
    nonexistent_file = tmp_path / "nonexistent.env"

    config = MarimoConfig(
        runtime={
            "dotenv": [str(nonexistent_file)],
        }
    )

    with pytest.raises(ValueError):
        write_secret(
            CreateSecretRequest(
                key="NEW_SECRET",
                value="new_value",
                provider="dotenv",
                name=str(nonexistent_file),
            ),
            config,
        )

    # Will write non existent file, if its the default .env file
    env_file = tmp_path / ".env"
    assert not env_file.exists()

    config = MarimoConfig(
        runtime={
            "dotenv": [str(tmp_path / ".env")],
        }
    )

    write_secret(
        CreateSecretRequest(
            key="NEW_SECRET",
            value="new_value",
            provider="dotenv",
            name=".env",
        ),
        config,
    )

    content = env_file.read_text()
    assert content == 'NEW_SECRET="new_value"\n'
