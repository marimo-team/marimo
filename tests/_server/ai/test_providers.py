"""Tests for the LLM providers in marimo._server.ai.providers."""

import pytest

from marimo._config.config import AiConfig
from marimo._server.ai.providers import (
    AnthropicProvider,
    AnyProviderConfig,
    BedrockProvider,
    GoogleProvider,
    OpenAIProvider,
    get_completion_provider,
)


@pytest.mark.parametrize(
    ("model_name", "provider_name"),
    [
        pytest.param("gpt-4", "openai", id="openai"),
        pytest.param("claude-3-opus-20240229", "anthropic", id="anthropic"),
        pytest.param("gemini-1.5-flash", "google", id="google"),
        pytest.param(
            "bedrock/anthropic.claude-3-sonnet-20240229",
            "bedrock",
            id="bedrock",
        ),
    ],
)
def test_anyprovider_for_model(model_name, provider_name):
    """Test that the correct config is returned for a given model."""
    ai_config = AiConfig(
        open_ai={
            "model": model_name,
            "api_key": "openai-key",
        },
        anthropic={
            "api_key": "anthropic-key",
        },
        google={
            "api_key": "google-key",
        },
        bedrock={
            "profile_name": "aws-profile",
        },
    )
    config = AnyProviderConfig.for_model(model_name, ai_config)

    if provider_name != "bedrock":
        assert config.api_key == f"{provider_name}-key"
    else:
        # bedrock overloads the api_key for profile name
        assert config.api_key == "profile:aws-profile"


@pytest.mark.parametrize(
    ("model_name", "provider_type"),
    [
        pytest.param("gpt-4", OpenAIProvider, id="openai"),
        pytest.param(
            "claude-3-opus-20240229", AnthropicProvider, id="anthropic"
        ),
        pytest.param("gemini-1.5-flash", GoogleProvider, id="google"),
        pytest.param(
            "bedrock/anthropic.claude-3-sonnet-20240229",
            BedrockProvider,
            id="bedrock",
        ),
    ],
)
def test_get_completion_provider(model_name, provider_type):
    """Test that the correct provider is returned for a given model."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = get_completion_provider(config, model_name)
    assert isinstance(provider, provider_type)
