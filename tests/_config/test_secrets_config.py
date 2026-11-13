from __future__ import annotations

from marimo._config.config import PartialMarimoConfig
from marimo._config.config_schema import MarimoConfig
from marimo._config.secrets import (
    SECRET_PLACEHOLDER,
    redact_secrets,
    redact_secrets_partial,
    remove_secret_placeholders,
)


def test_redact_typed_config() -> None:
    config = MarimoConfig.from_dict(
        {
            "ai": {
                "open_ai": {"api_key": "openai-secret"},
                "custom_providers": {
                    "gateway": {
                        "api_key": "gateway-secret",
                        "base_url": "https://example.com",
                    }
                },
                "bedrock": {
                    "aws_access_key_id": "access-key",
                    "aws_secret_access_key": "secret-key",
                },
            },
            "server": {"session_secret": "session-secret"},
            "runtime": {"dotenv": [".env"]},
            "signing": {"private_key_path": "private.pem"},
        }
    )
    original = config.to_dict()
    expected = config.to_dict()
    expected["ai"]["open_ai"]["api_key"] = SECRET_PLACEHOLDER
    expected["ai"]["custom_providers"]["gateway"]["api_key"] = (
        SECRET_PLACEHOLDER
    )
    expected["ai"]["bedrock"]["aws_access_key_id"] = SECRET_PLACEHOLDER
    expected["ai"]["bedrock"]["aws_secret_access_key"] = SECRET_PLACEHOLDER
    expected["server"]["session_secret"] = SECRET_PLACEHOLDER
    expected["signing"]["private_key_path"] = SECRET_PLACEHOLDER
    del expected["runtime"]["dotenv"]

    redacted = redact_secrets(config)

    assert isinstance(redacted, MarimoConfig)
    assert redacted.to_dict() == expected
    assert config.to_dict() == original


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

    new_config = redact_secrets_partial(config)
    assert "dotenv" not in new_config["runtime"]
    assert config["runtime"]["dotenv"] == [".env"]
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
    new_config = redact_secrets_partial(config)
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

    new_config = redact_secrets_partial(config)
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
    new_config = redact_secrets_partial(config)
    assert new_config["ai"]["open_ai"]["api_key"] == ""
    assert new_config["ai"]["google"]["api_key"] == ""
    assert new_config["ai"]["anthropic"]["api_key"] == ""
    assert new_config["ai"]["openrouter"]["api_key"] == ""
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == ""
    assert config["ai"]["google"]["api_key"] == ""
    assert config["ai"]["anthropic"]["api_key"] == ""
    assert config["ai"]["openrouter"]["api_key"] == ""


def test_mask_secrets_non_dict_values() -> None:
    """redact_secrets must not crash when a secret path hits a non-dict value.

    A malformed/partial config can place a non-dict where redact_secrets expects
    to recurse into a dict. `bedrock=None` previously raised TypeError and
    `custom_providers="oops"` raised AttributeError; valid providers must still
    be masked.
    """
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"api_key": "super_secret"},
            "bedrock": None,
            "custom_providers": "oops",
        },
    )
    new_config = redact_secrets_partial(config)
    assert new_config["ai"]["open_ai"]["api_key"] == SECRET_PLACEHOLDER
    assert new_config["ai"]["bedrock"] is None
    assert new_config["ai"]["custom_providers"] == "oops"


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
    new_config = redact_secrets_partial(config)

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


def test_mask_secrets_signing_private_key_path() -> None:
    """private_key_path is masked so it is never serialized to the frontend."""
    config = PartialMarimoConfig(
        signing={
            "private_key_path": "/home/user/.marimo/key.pem",
            "trusted_signers": {"SHA256:abc": "alice"},
        },
    )
    masked = redact_secrets_partial(config)
    assert masked["signing"]["private_key_path"] == SECRET_PLACEHOLDER
    # trusted_signers are public fingerprints — not masked.
    assert masked["signing"]["trusted_signers"] == {"SHA256:abc": "alice"}
    # A frontend round-trip (placeholder back to us) must not overwrite the
    # real path on save.
    assert "private_key_path" not in remove_secret_placeholders(masked).get(
        "signing", {}
    )


def test_removed_codeium_credentials_are_not_exposed() -> None:
    config = {
        "completion": {
            "codeium_api_key": "legacy-secret",
            "auto_close_pairs": False,
        }
    }
    assert redact_secrets_partial(config) == {
        "completion": {"auto_close_pairs": False}
    }
    assert redact_secrets(
        MarimoConfig.from_dict(config)
    ).completion.to_dict() == {
        "activate_on_typing": True,
        "signature_hint_on_typing": False,
        "copilot": False,
        "auto_close_pairs": False,
    }
    assert config == {
        "completion": {
            "codeium_api_key": "legacy-secret",
            "auto_close_pairs": False,
        }
    }
