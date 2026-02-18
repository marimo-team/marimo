"""Tests for the LLM providers in marimo._server.ai.providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._config.config import AiConfig
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.providers import (
    AnthropicProvider,
    AzureOpenAIProvider,
    BedrockProvider,
    CustomProvider,
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
            "claude-3-opus-20240229",
            AnthropicProvider,
            DependencyManager.anthropic,
            id="anthropic",
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
            DependencyManager.boto3,
            id="bedrock",
        ),
        pytest.param(
            "openrouter/gpt-4", CustomProvider, None, id="openrouter"
        ),
    ],
)
def test_get_completion_provider(
    model_name: str, provider_type: type, dependency: Dependency | None
) -> None:
    """Test that the correct provider is returned for a given model."""

    if not DependencyManager.pydantic_ai.has():
        pytest.skip("requires pydantic_ai")

    if dependency and not dependency.has():
        pytest.skip(f"{dependency.pkg} is not installed")

    if provider_type == BedrockProvider:
        # For Bedrock, we pass bedrock-required details through the config
        config = AnyProviderConfig(
            api_key="aws_access_key_id:aws_secret_access_key",  # credentials
            base_url="us-east-1",  # region name
        )
    else:
        config = AnyProviderConfig(
            api_key="test-key", base_url="http://test-url"
        )
    provider = get_completion_provider(config, model_name)
    assert isinstance(provider, provider_type)


@pytest.mark.requires("pydantic_ai")
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


@pytest.mark.skipif(
    not DependencyManager.anthropic.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="anthropic or pydantic_ai not installed",
)
def test_anthropic_process_part_text_file() -> None:
    """Test Anthropic converts text file parts to text parts."""
    from pydantic_ai.ui.vercel_ai.request_types import FileUIPart, TextUIPart

    config = AnyProviderConfig(api_key="test-key", base_url="http://test")
    provider = AnthropicProvider("claude-3-opus-20240229", config)

    # Test text file conversion - base64 encoded "Hello, World!"
    text_file_part = FileUIPart(
        type="file",
        media_type="text/plain",
        url="data:text/plain;base64,SGVsbG8sIFdvcmxkIQ==",
        filename="test.txt",
    )
    result = provider.process_part(text_file_part)
    assert isinstance(result, TextUIPart)
    assert result.text == "Hello, World!"

    # Test image file is not converted
    image_file_part = FileUIPart(
        type="file",
        media_type="image/png",
        url="data:image/png;base64,iVBORw0KGgo=",
        filename="test.png",
    )
    result = provider.process_part(image_file_part)
    assert isinstance(result, FileUIPart)
    assert result.media_type == "image/png"


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
@pytest.mark.requires("pydantic_ai")
def test_is_reasoning_model(
    model_name: str, base_url: str | None, expected: bool
) -> None:
    """Test that _is_reasoning_model correctly identifies reasoning models."""
    config = AnyProviderConfig(api_key="test-key", base_url=base_url)
    provider = OpenAIProvider(model_name, config)
    assert provider._is_reasoning_model(model_name) == expected


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        pytest.param(
            "claude-opus-4-20250514",
            True,
            id="claude_opus_4",
        ),
        pytest.param(
            "claude-sonnet-4-20250514",
            True,
            id="claude_sonnet_4",
        ),
        pytest.param(
            "claude-haiku-4-5-20250514",
            True,
            id="claude_haiku_4_5",
        ),
        pytest.param(
            "claude-3-7-sonnet-20250219",
            True,
            id="claude_3_7_sonnet",
        ),
        pytest.param(
            "claude-3-5-sonnet-20241022",
            False,
            id="claude_3_5_sonnet_not_thinking",
        ),
        pytest.param(
            "claude-3-opus-20240229",
            False,
            id="claude_3_opus_not_thinking",
        ),
    ],
)
@pytest.mark.skipif(
    not DependencyManager.anthropic.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="anthropic or pydantic_ai not installed",
)
def test_anthropic_is_extended_thinking_model(
    model_name: str, expected: bool
) -> None:
    """Test that is_extended_thinking_model correctly identifies thinking models."""
    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider(model_name, config)
    assert provider.is_extended_thinking_model(model_name) == expected


@pytest.mark.requires("pydantic_ai")
@pytest.mark.xfail(
    reason="System prompt is duplicated when passed to both Agent constructor and run()"
)
async def test_completion_does_not_pass_redundant_instructions() -> None:
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.openai import OpenAIResponsesModel

    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)

    with (
        patch("marimo._server.ai.providers.get_tool_manager") as mock_get_tm,
        patch.object(
            OpenAIResponsesModel, "request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_get_tm.return_value = MagicMock()
        mock_request.return_value = ModelResponse(
            parts=[TextPart(content="test")]
        )

        await provider.completion(
            messages=[],
            system_prompt="Test prompt",
            max_tokens=100,
            additional_tools=[],
        )

        mock_request.assert_called_once()
        request_messages = mock_request.call_args.args[0]

        assert len(request_messages) == 1
        # The bug caused instructions to be "Test prompt\nTest prompt"
        instructions = request_messages[0].instructions

        # This asserts the duplication is gone
        assert instructions == "Test prompt"
