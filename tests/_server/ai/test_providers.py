"""Tests for the LLM providers in marimo._server.ai.providers."""

from unittest.mock import AsyncMock, patch

import pytest

from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig
from marimo._server.ai.providers import (
    AnthropicProvider,
    AnyProviderConfig,
    AzureOpenAIProvider,
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
        pytest.param("openrouter/gpt-4", "openrouter", id="openrouter"),
    ],
)
def test_anyprovider_for_model(model_name: str, provider_name: str) -> None:
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
        openrouter={
            "api_key": "openrouter-key",
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
        pytest.param("openrouter/gpt-4", OpenAIProvider, id="openrouter"),
    ],
)
def test_get_completion_provider(model_name: str, provider_type: type) -> None:
    """Test that the correct provider is returned for a given model."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = get_completion_provider(config, model_name)
    assert isinstance(provider, provider_type)


@pytest.mark.parametrize(
    ("model_name", "expected_params"),
    [
        pytest.param(
            "o1-mini",
            {"max_completion_tokens": 1000, "reasoning_effort": "medium"},
            id="reasoning_model_o1_mini",
        ),
        pytest.param(
            "o1-preview",
            {"max_completion_tokens": 1000, "reasoning_effort": "medium"},
            id="reasoning_model_o1_preview",
        ),
        pytest.param(
            "gpt-4",
            {"max_tokens": 1000},
            id="non_reasoning_model_gpt4",
        ),
        pytest.param(
            "gpt-3.5-turbo",
            {"max_tokens": 1000},
            id="non_reasoning_model_gpt35",
        ),
    ],
)
@patch("openai.AsyncOpenAI")
async def test_openai_provider_max_tokens_parameter(
    mock_openai_class, model_name: str, expected_params: dict
) -> None:
    """Test that OpenAI provider uses correct token parameter for reasoning vs non-reasoning models."""
    # Setup mock
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    mock_stream = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    # Create provider
    config = AnyProviderConfig(
        api_key="test-key", base_url="https://api.openai.com/v1"
    )
    provider = OpenAIProvider(model_name, config)

    # Call stream_completion
    messages = [ChatMessage(role="user", content="test message")]
    await provider.stream_completion(messages, "system prompt", 1000)

    # Verify the correct parameters were passed
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]

    # Check that the expected parameters are present
    for param_name, param_value in expected_params.items():
        assert param_name in call_kwargs, (
            f"Expected parameter {param_name} not found"
        )
        assert call_kwargs[param_name] == param_value

    # Ensure mutually exclusive parameters are not both present
    if "max_completion_tokens" in expected_params:
        assert "max_tokens" not in call_kwargs, (
            "max_tokens should not be present for reasoning models"
        )
    else:
        assert "max_completion_tokens" not in call_kwargs, (
            "max_completion_tokens should not be present for non-reasoning models"
        )


async def test_azure_openai_provider() -> None:
    """Test that Azure OpenAI provider uses correct parameters."""
    config = AnyProviderConfig(
        api_key="test-key",
        base_url="https://test.openai.azure.com/gpt-4-1?api-version=2023-05-15",
    )
    provider = AzureOpenAIProvider("gpt-4", config)

    api_version, deployment_name, endpoint = provider._handle_azure_openai(
        "https://test.openai.azure.com/gpt-4-1?api-version=2023-05-15"
    )
    assert api_version == "2023-05-15"
    assert deployment_name == "gpt-4-1"
    assert endpoint == "https://test.openai.azure.com"
