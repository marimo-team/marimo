"""Tests for the LLM providers in marimo._server.ai.providers."""

from unittest.mock import AsyncMock, MagicMock, patch

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
    await provider.stream_completion(messages, "system prompt", 1000, [])

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
        base_url="https://test.openai.azure.com/openai/deployments/gpt-4-1?api-version=2023-05-15",
    )
    provider = AzureOpenAIProvider("gpt-4", config)

    api_version, deployment_name, endpoint = provider._handle_azure_openai(
        "https://test.openai.azure.com/openai/deployments/gpt-4-1?api-version=2023-05-15"
    )
    assert api_version == "2023-05-15"
    assert deployment_name == "gpt-4-1"
    assert endpoint == "https://test.openai.azure.com"

    api_version, deployment_name, endpoint = provider._handle_azure_openai(
        "https://unknown_domain.openai/openai/deployments/gpt-4-1?api-version=2023-05-15"
    )
    assert api_version == "2023-05-15"
    assert deployment_name == "gpt-4-1"
    assert endpoint == "https://unknown_domain.openai"


@pytest.mark.parametrize(
    "provider_type",
    [
        pytest.param(OpenAIProvider, id="openai"),
        pytest.param(BedrockProvider, id="bedrock"),
    ],
)
def test_extract_content_with_none_tool_call_ids(
    provider_type: type,
) -> None:
    """Test extract_content handles None tool_call_ids without errors."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = provider_type("test-model", config)

    mock_response = MagicMock()
    mock_delta = MagicMock()
    mock_delta.content = "Hello"
    mock_delta.tool_calls = None
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    mock_response.choices = [mock_choice]

    result = provider.extract_content(mock_response, None)
    assert result == [("Hello", "text")]


def test_google_extract_content_with_none_tool_call_ids() -> None:
    """Test Google extract_content handles None tool_call_ids without errors."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = GoogleProvider("gemini-1.5-flash", config)

    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_content = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "Hello"
    mock_part.thought = False
    mock_part.function_call = None
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    mock_response.candidates = [mock_candidate]

    result = provider.extract_content(mock_response, None)
    assert result == [("Hello", "text")]


def test_openai_extract_content_multiple_tool_calls() -> None:
    """Test OpenAI extracts multiple tool calls correctly."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = OpenAIProvider("gpt-4", config)

    mock_response = MagicMock()
    mock_delta = MagicMock()
    mock_delta.content = None

    mock_tool_1 = MagicMock()
    mock_tool_1.index = 0
    mock_tool_1.id = "call_1"
    mock_tool_1.function = MagicMock()
    mock_tool_1.function.name = "get_weather"
    mock_tool_1.function.arguments = None

    mock_tool_2 = MagicMock()
    mock_tool_2.index = 1
    mock_tool_2.id = "call_2"
    mock_tool_2.function = MagicMock()
    mock_tool_2.function.name = "get_time"
    mock_tool_2.function.arguments = None

    mock_delta.tool_calls = [mock_tool_1, mock_tool_2]
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    mock_response.choices = [mock_choice]

    result = provider.extract_content(mock_response, None)
    assert result is not None
    assert len(result) == 2
    tool_data_0, _ = result[0]
    tool_data_1, _ = result[1]
    assert isinstance(tool_data_0, dict)
    assert isinstance(tool_data_1, dict)
    assert tool_data_0["toolName"] == "get_weather"
    assert tool_data_1["toolName"] == "get_time"


def test_google_extract_content_id_rectification() -> None:
    """Test Google uses provided tool_call_ids for ID rectification."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = GoogleProvider("gemini-1.5-flash", config)

    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_content = MagicMock()
    mock_func_call = MagicMock()
    mock_func_call.name = "get_weather"
    mock_func_call.args = {"location": "SF"}
    mock_func_call.id = None
    mock_part = MagicMock()
    mock_part.text = None
    mock_part.function_call = mock_func_call
    mock_content.parts = [mock_part]
    mock_candidate.content = mock_content
    mock_response.candidates = [mock_candidate]

    result = provider.extract_content(mock_response, ["stable_id"])
    assert result is not None
    tool_data, _ = result[0]
    assert isinstance(tool_data, dict)
    assert tool_data["toolCallId"] == "stable_id"


def test_anthropic_extract_content_tool_call_id_mapping() -> None:
    """Test Anthropic maps tool call IDs via block index."""
    try:
        from anthropic.types import (
            InputJSONDelta,
            RawContentBlockDeltaEvent,
            RawContentBlockStartEvent,
            ToolUseBlock,
        )
    except ImportError:
        pytest.skip("Anthropic not installed")

    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = AnthropicProvider("claude-3-opus-20240229", config)

    start_event = RawContentBlockStartEvent(
        type="content_block_start",
        index=0,
        content_block=ToolUseBlock(
            type="tool_use", id="toolu_123", name="get_weather", input={}
        ),
    )
    provider.extract_content(start_event, None)

    delta_event = RawContentBlockDeltaEvent(
        type="content_block_delta",
        index=0,
        delta=InputJSONDelta(
            type="input_json_delta", partial_json='{"location": "SF"}'
        ),
    )
    result = provider.extract_content(delta_event, None)
    assert result is not None
    tool_data, _ = result[0]
    assert isinstance(tool_data, dict)
    assert tool_data["toolCallId"] == "toolu_123"
