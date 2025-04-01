from __future__ import annotations

from marimo._config.config import PartialMarimoConfig
from marimo._config.secrets import mask_secrets, remove_secret_placeholders


def test_mask_secrets() -> None:
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"api_key": "super_secret"},
            "anthropic": {"api_key": "anthropic_secret"},
            "google": {"api_key": "google_secret"},
        },
        runtime={
            "dotenv": [".env"],
        },
    )
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert config["ai"]["anthropic"]["api_key"] == "anthropic_secret"
    assert config["ai"]["google"]["api_key"] == "google_secret"

    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == "********"
    assert new_config["ai"]["anthropic"]["api_key"] == "********"
    assert new_config["ai"]["google"]["api_key"] == "********"

    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "super_secret"
    assert config["ai"]["anthropic"]["api_key"] == "anthropic_secret"
    assert config["ai"]["google"]["api_key"] == "google_secret"


def test_mask_secrets_empty() -> None:
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"model": "davinci"},
            "google": {},
            "anthropic": {},
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
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["model"] == "davinci"

    # Not added when key is ""
    config["ai"]["open_ai"]["api_key"] = ""
    config["ai"]["google"]["api_key"] = ""
    config["ai"]["anthropic"]["api_key"] = ""
    new_config = mask_secrets(config)
    assert new_config["ai"]["open_ai"]["api_key"] == ""
    assert new_config["ai"]["google"]["api_key"] == ""
    assert new_config["ai"]["anthropic"]["api_key"] == ""
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == ""
    assert config["ai"]["google"]["api_key"] == ""
    assert config["ai"]["anthropic"]["api_key"] == ""


def test_remove_secret_placeholders() -> None:
    config = PartialMarimoConfig(
        ai={
            "open_ai": {"api_key": "********"},
            "google": {"api_key": "********"},
            "anthropic": {"api_key": "********"},
        },
    )
    assert config["ai"]["open_ai"]["api_key"] == "********"
    assert config["ai"]["google"]["api_key"] == "********"
    assert config["ai"]["anthropic"]["api_key"] == "********"
    new_config = remove_secret_placeholders(config)
    assert "api_key" not in new_config["ai"]["open_ai"]
    assert "api_key" not in new_config["ai"]["google"]
    assert "api_key" not in new_config["ai"]["anthropic"]
    # Ensure the original config is not modified
    assert config["ai"]["open_ai"]["api_key"] == "********"
    assert config["ai"]["google"]["api_key"] == "********"
    assert config["ai"]["anthropic"]["api_key"] == "********"
