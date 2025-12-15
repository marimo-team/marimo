"""Tests for the LLM providers in marimo._server.ai.providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._ai._types import ChatMessage
from marimo._config.config import AiConfig
from marimo._server.ai.config import AnyProviderConfig
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._server.ai.providers import (
    AnthropicProvider,
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
    ("model_name", "provider_type", "dependency"),
    [
        pytest.param("gpt-4", OpenAIProvider, None, id="openai"),
        pytest.param(
            "claude-3-opus-20240229", AnthropicProvider, None, id="anthropic"
        ),
        pytest.param(
            "gemini-1.5-flash",
            GoogleProvider,
            DependencyManager.google_ai,
            id="google",
        ),
        pytest.param(
            "bedrock/anthropic.claude-3-sonnet-20240229",
            BedrockProvider,
            None,
            id="bedrock",
        ),
        pytest.param(
            "openrouter/gpt-4", OpenAIProvider, None, id="openrouter"
        ),
    ],
)
def test_get_completion_provider(
    model_name: str, provider_type: type, dependency: Dependency | None
) -> None:
    """Test that the correct provider is returned for a given model."""

    if dependency and not dependency.has():
        pytest.skip(f"{dependency.pkg} is not installed")

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


@pytest.mark.parametrize(
    ("model_name", "base_url", "expected"),
    [
        pytest.param(
            "o1-mini",
            None,
            True,
            id="o1_mini_no_base_url",
        ),
        pytest.param(
            "o1-preview",
            None,
            True,
            id="o1_preview_no_base_url",
        ),
        pytest.param(
            "o1",
            None,
            True,
            id="o1_no_base_url",
        ),
        pytest.param(
            "o1-2024-12-17",
            "https://api.openai.com/v1",
            True,
            id="o1_dated_openai_base_url",
        ),
        pytest.param(
            "o3-mini",
            None,
            True,
            id="o3_mini_no_base_url",
        ),
        pytest.param(
            "gpt-5-turbo",
            None,
            True,
            id="gpt5_turbo_no_base_url",
        ),
        pytest.param(
            "gpt-5-preview",
            None,
            True,
            id="gpt5_preview_no_base_url",
        ),
        pytest.param(
            "openai/o1-mini",
            None,
            True,
            id="openai_prefix_o1_mini_no_base_url",
        ),
        pytest.param(
            "openai/o1-preview",
            None,
            True,
            id="openai_prefix_o1_preview_no_base_url",
        ),
        pytest.param(
            "openai/gpt-5-turbo",
            None,
            True,
            id="openai_prefix_gpt5_no_base_url",
        ),
        pytest.param(
            "o1-mini",
            "https://custom.api.com/v1",
            False,
            id="o1_custom_base_url",
        ),
        pytest.param(
            "o1-preview",
            "https://litellm.proxy.com/api/v1",
            False,
            id="o1_litellm_proxy",
        ),
        pytest.param(
            "gpt-4",
            None,
            False,
            id="gpt4_no_base_url",
        ),
        pytest.param(
            "gpt-4o",
            None,
            False,
            id="gpt4o_no_base_url",
        ),
        pytest.param(
            "gpt-4",
            "https://custom.api.com/v1",
            False,
            id="gpt4_custom_base_url",
        ),
        pytest.param(
            "olive-model",
            None,
            False,
            id="model_starting_with_o_but_not_reasoning",
        ),
        pytest.param(
            "openrouter/o1-mini",
            None,
            False,
            id="openrouter_prefix_not_openai",
        ),
    ],
)
def test_is_reasoning_model(
    model_name: str, base_url: str | None, expected: bool
) -> None:
    """Test that _is_reasoning_model correctly identifies reasoning models."""
    config = AnyProviderConfig(api_key="test-key", base_url=base_url)
    provider = OpenAIProvider(model_name, config)
    assert provider._is_reasoning_model(model_name) == expected


@pytest.mark.parametrize(
    ("model_name", "base_url", "expected_params"),
    [
        pytest.param(
            "o1-mini",
            "https://custom-openai-compatible.com/v1",
            {"max_tokens": 1000},
            id="reasoning_model_name_custom_api_no_reasoning",
        ),
        pytest.param(
            "o1-preview",
            "https://litellm.proxy.com/api/v1",
            {"max_tokens": 1000},
            id="o1_preview_litellm_proxy_no_reasoning",
        ),
        pytest.param(
            "o3-mini",
            "https://corporate-llm.internal/api",
            {"max_tokens": 1000},
            id="o3_mini_corporate_proxy_no_reasoning",
        ),
    ],
)
@patch("openai.AsyncOpenAI")
async def test_openai_compatible_api_no_reasoning_effort(
    mock_openai_class, model_name: str, base_url: str, expected_params: dict
) -> None:
    """Test that OpenAI-compatible APIs don't get reasoning_effort even with reasoning model names."""
    # Setup mock
    mock_client = AsyncMock()
    mock_openai_class.return_value = mock_client
    mock_stream = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    # Create provider with custom base_url (simulating OpenAI-compatible API)
    config = AnyProviderConfig(api_key="test-key", base_url=base_url)
    provider = OpenAIProvider(model_name, config)

    # Call stream_completion
    messages = [ChatMessage(role="user", content="test message")]
    await provider.stream_completion(messages, "system prompt", 1000, [])

    # Verify the correct parameters were passed
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]

    # Check that reasoning_effort is NOT present
    assert "reasoning_effort" not in call_kwargs, (
        "reasoning_effort should not be present for OpenAI-compatible APIs"
    )

    # Check that the expected parameters are present
    for param_name, param_value in expected_params.items():
        assert param_name in call_kwargs, (
            f"Expected parameter {param_name} not found"
        )
        assert call_kwargs[param_name] == param_value

    # Ensure max_completion_tokens is not present when reasoning_effort is not used
    assert "max_completion_tokens" not in call_kwargs, (
        "max_completion_tokens should not be present when reasoning_effort is not used"
    )


def test_openai_extract_content_tool_delta_out_of_bounds() -> None:
    """Test OpenAI handles tool call delta with out-of-bounds index gracefully.

    This reproduces the issue reported in #7330 where some OpenAI-compatible
    providers (like deepseek) may send tool call deltas before the tool call
    start, causing an IndexError.
    """
    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = OpenAIProvider("gpt-4", config)

    mock_response = MagicMock()
    mock_delta = MagicMock()
    mock_delta.content = None

    # Create a tool call delta with index 0, but tool_call_ids is empty
    mock_tool_delta = MagicMock()
    mock_tool_delta.index = 0
    mock_tool_delta.id = None  # No id for delta chunks
    mock_tool_delta.function = MagicMock()
    mock_tool_delta.function.name = None  # No name for delta chunks
    mock_tool_delta.function.arguments = '{"location": "SF"}'

    mock_delta.tool_calls = [mock_tool_delta]
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    mock_response.choices = [mock_choice]

    # Call with empty tool_call_ids - this should not crash
    result = provider.extract_content(mock_response, [])
    # Should return None or empty list since we can't process the delta
    assert result is None or result == []


def test_bedrock_extract_content_tool_delta_out_of_bounds() -> None:
    """Test Bedrock handles tool call delta with out-of-bounds index gracefully.

    This reproduces the issue reported in #7330 where some providers may send
    tool call deltas before the tool call start, causing an IndexError.
    """
    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = BedrockProvider("bedrock/anthropic.claude-3-sonnet", config)

    mock_response = MagicMock()
    mock_delta = MagicMock()
    mock_delta.content = None

    # Create a tool call delta with index 0, but tool_call_ids is empty
    mock_tool_delta = MagicMock()
    mock_tool_delta.index = 0
    mock_tool_delta.id = None  # No id for delta chunks
    mock_tool_delta.function = MagicMock()
    mock_tool_delta.function.name = None  # No name for delta chunks
    mock_tool_delta.function.arguments = '{"location": "SF"}'

    mock_delta.tool_calls = [mock_tool_delta]
    mock_choice = MagicMock()
    mock_choice.delta = mock_delta
    mock_response.choices = [mock_choice]

    # Call with empty tool_call_ids - this should not crash
    result = provider.extract_content(mock_response, [])
    # Should return None or empty list since we can't process the delta
    assert result is None or result == []
