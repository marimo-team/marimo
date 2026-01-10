from __future__ import annotations

from marimo._config.config import PartialMarimoConfig
from marimo._config.secrets import (
    SECRET_PLACEHOLDER,
    mask_secrets,
    remove_secret_placeholders,
)


def test_mask_secrets() -> None:
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"api_key": "super_secret"},
            "anthropic": {"api_key": "anthropic_secret"},
            "google": {"api_key": "google_secret"},
            "github": {"api_key": "github_secret"},
            "openrouter": {"api_key": "openrouter_secret"},
            "bedrock": {
                "aws_access_key_id": "bedrock_access_key_id",
                "aws_secret_access_key": "bedrock_secret_access_key",
            },
        },
        runtime={
            "dotenv": [".env"],
        },
    )
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert config["ai"]["anthropic"]["api_key"] == "anthropic_secret"
    assert config["ai"]["google"]["api_key"] == "google_secret"
    assert config["ai"]["github"]["api_key"] == "github_secret"
    assert config["ai"]["openrouter"]["api_key"] == "openrouter_secret"
    assert (
        config["ai"]["bedrock"]["aws_access_key_id"] == "bedrock_access_key_id"
    )
    assert (
        config["ai"]["bedrock"]["aws_secret_access_key"]
        == "bedrock_secret_access_key"
    )

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == SECRET_PLACEHOLDER
    assert new_config["ai"]["anthropic"]["api_key"] == SECRET_PLACEHOLDER
    assert new_config["ai"]["google"]["api_key"] == SECRET_PLACEHOLDER
    assert new_config["ai"]["github"]["api_key"] == SECRET_PLACEHOLDER
    assert new_config["ai"]["openrouter"]["api_key"] == SECRET_PLACEHOLDER
    assert (
        new_config["ai"]["bedrock"]["aws_access_key_id"] == SECRET_PLACEHOLDER
    )
    assert (
        new_config["ai"]["bedrock"]["aws_secret_access_key"]
        == SECRET_PLACEHOLDER
    )

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert config["ai"]["anthropic"]["api_key"] == "anthropic_secret"
    assert config["ai"]["google"]["api_key"] == "google_secret"
    assert config["ai"]["github"]["api_key"] == "github_secret"
    assert config["ai"]["openrouter"]["api_key"] == "openrouter_secret"
    assert (
        config["ai"]["bedrock"]["aws_access_key_id"] == "bedrock_access_key_id"
    )
    assert (
        config["ai"]["bedrock"]["aws_secret_access_key"]
        == "bedrock_secret_access_key"
    )


def test_mask_secrets_list() -> None:
    config = PartialMarimoConfig(
        ai={"open_ai": [{"api_key": "super_secret"}]},
    )
    assert config["ai"]["open_ai"][0]["api_key"] == "super_secret"
    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"][0]["api_key"] == SECRET_PLACEHOLDER

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"][0]["api_key"] == "super_secret"


def test_mask_secrets_empty() -> None:
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"model": "davinci"},
            "google": {},
            "anthropic": {},
            "openrouter": {},
        },
        runtime={
            "dotenv": [],
        },
    )
    assert config["ai"]["open_ai"]["model"] == "davinci"

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["model"] == "davinci"
    # Not added until the key is present
    assert "api_key" not in new_config["ai"]["open_ai"]
    assert "api_key" not in new_config["ai"]["google"]
    assert "api_key" not in new_config["ai"]["anthropic"]
    assert "api_key" not in new_config["ai"]["openrouter"]
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["model"] == "davinci"

    # Not added when key is ""
    config["ai"]["open_ai"]["api_key"] = ""
    config["ai"]["google"]["api_key"] = ""
    config["ai"]["anthropic"]["api_key"] = ""
    config["ai"]["openrouter"]["api_key"] = ""
    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == ""
    assert new_config["ai"]["google"]["api_key"] == ""
    assert new_config["ai"]["anthropic"]["api_key"] == ""
    assert new_config["ai"]["openrouter"]["api_key"] == ""
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == ""
    assert config["ai"]["google"]["api_key"] == ""
    assert config["ai"]["anthropic"]["api_key"] == ""
    assert config["ai"]["openrouter"]["api_key"] == ""


def test_remove_secret_placeholders() -> None:
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"api_key": SECRET_PLACEHOLDER},
            "google": {"api_key": SECRET_PLACEHOLDER},
            "anthropic": {"api_key": SECRET_PLACEHOLDER},
            "openrouter": {"api_key": SECRET_PLACEHOLDER},
        },
    )
    assert config["ai"]["open_ai"]["api_key"] == SECRET_PLACEHOLDER
    assert config["ai"]["google"]["api_key"] == SECRET_PLACEHOLDER
    assert config["ai"]["anthropic"]["api_key"] == SECRET_PLACEHOLDER
    assert config["ai"]["openrouter"]["api_key"] == SECRET_PLACEHOLDER
    new_config = remove_secret_placeholders(config)
    assert "api_key" not in new_config["ai"]["open_ai"]
    assert "api_key" not in new_config["ai"]["google"]
    assert "api_key" not in new_config["ai"]["anthropic"]
    assert "api_key" not in new_config["ai"]["openrouter"]
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == SECRET_PLACEHOLDER
    assert config["ai"]["google"]["api_key"] == SECRET_PLACEHOLDER
    assert config["ai"]["anthropic"]["api_key"] == SECRET_PLACEHOLDER
    assert config["ai"]["openrouter"]["api_key"] == SECRET_PLACEHOLDER


def test_mask_secrets_custom_providers() -> None:
    """Test that custom_providers api_keys are masked."""
    config = PartialMarimoConfig(
        ai={
            "custom_providers": {
                "groq": {
                    "api_key": "gsk-super-secret-groq-key",
                    "base_url": "https://api.groq.com/openai/v1",
                },
                "together": {
                    "api_key": "tg-super-secret-together-key",
                    "base_url": "https://api.together.xyz/v1",
                },
                "local_provider": {
                    "base_url": "http://localhost:8000/v1",
                    # no api_key
                },
            },
        },
    )

    # Verify original values
    assert (
        config["ai"]["custom_providers"]["groq"]["api_key"]
        == "gsk-super-secret-groq-key"
    )
    assert (
        config["ai"]["custom_providers"]["together"]["api_key"]
        == "tg-super-secret-together-key"
    )

    # Mask secrets
    new_config = mask_secrets(config)

    # Verify api_keys are masked
    assert (
        new_config["ai"]["custom_providers"]["groq"]["api_key"]
        == SECRET_PLACEHOLDER
    )
    assert (
        new_config["ai"]["custom_providers"]["together"]["api_key"]
        == SECRET_PLACEHOLDER
    )

    # Verify base_url is not masked
    assert (
        new_config["ai"]["custom_providers"]["groq"]["base_url"]
        == "https://api.groq.com/openai/v1"
    )
    assert (
        new_config["ai"]["custom_providers"]["together"]["base_url"]
        == "https://api.together.xyz/v1"
    )

    # Verify provider without api_key is unchanged
    assert (
        new_config["ai"]["custom_providers"]["local_provider"]["base_url"]
        == "http://localhost:8000/v1"
    )
    assert (
        "api_key" not in new_config["ai"]["custom_providers"]["local_provider"]
    )

    # Ensure the original config is not modified
    assert (
        config["ai"]["custom_providers"]["groq"]["api_key"]
        == "gsk-super-secret-groq-key"
    )
    assert (
        config["ai"]["custom_providers"]["together"]["api_key"]
        == "tg-super-secret-together-key"
    )


def test_remove_secret_placeholders_custom_providers() -> None:
    """Test that custom_providers secret placeholders are removed."""
    config = PartialMarimoConfig(
        ai={
            "custom_providers": {
                "groq": {
                    "api_key": SECRET_PLACEHOLDER,
                    "base_url": "https://api.groq.com/openai/v1",
                },
            },
        },
    )
    assert (
        config["ai"]["custom_providers"]["groq"]["api_key"]
        == SECRET_PLACEHOLDER
    )

    new_config = remove_secret_placeholders(config)

    # api_key should be removed
    assert "api_key" not in new_config["ai"]["custom_providers"]["groq"]
    # base_url should still be there
    assert (
        new_config["ai"]["custom_providers"]["groq"]["base_url"]
        == "https://api.groq.com/openai/v1"
    )

    # Ensure the original config is not modified
    assert (
        config["ai"]["custom_providers"]["groq"]["api_key"]
        == SECRET_PLACEHOLDER
    )
