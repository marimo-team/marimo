"""Tests for the LLM providers in marimo._server.ai.providers."""

from typing import Any
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
    ("provider_kind", "model_name", "base_url", "expected_thinking"),
    [
        # OpenAI: profile drives the decision via supports_thinking.
        pytest.param("openai", "o1-mini", None, True, id="openai_o1_mini"),
        pytest.param(
            "openai",
            "o1-preview",
            "https://api.openai.com/v1",
            True,
            id="openai_o1_preview_official_url",
        ),
        pytest.param("openai", "o3", None, True, id="openai_o3"),
        pytest.param("openai", "o3-mini", None, True, id="openai_o3_mini"),
        pytest.param("openai", "gpt-5", None, True, id="openai_gpt5"),
        pytest.param(
            "openai", "gpt-4", None, False, id="openai_gpt4_no_thinking"
        ),
        pytest.param(
            "openai", "gpt-4o", None, False, id="openai_gpt4o_no_thinking"
        ),
        # Custom base URL (litellm/vLLM/Together/etc.) suppresses thinking
        # even when the model name looks like a reasoning model: third-party
        # endpoints often don't accept `reasoning_effort`.
        pytest.param(
            "openai",
            "o1-mini",
            "https://custom.api.com/v1",
            False,
            id="openai_o1_custom_base_url",
        ),
        pytest.param(
            "openai",
            "gpt-5",
            "https://litellm.proxy.com/api/v1",
            False,
            id="openai_gpt5_litellm_proxy",
        ),
        # Azure: thinking is always suppressed (only custom Azure deployments
        # support reasoning_effort, which we don't expose yet).
        pytest.param(
            "azure",
            "o1-mini",
            "https://my.openai.azure.com/openai/deployments/o1-mini?api-version=2024-12-01-preview",
            False,
            id="azure_o1_mini",
        ),
        pytest.param(
            "azure",
            "gpt-5",
            "https://my.openai.azure.com/openai/deployments/gpt-5?api-version=2024-12-01-preview",
            False,
            id="azure_gpt5",
        ),
    ],
)
@pytest.mark.requires("pydantic_ai")
def test_openai_default_thinking(
    provider_kind: str,
    model_name: str,
    base_url: str | None,
    expected_thinking: bool,
) -> None:
    """The base url heuristic + pydantic-ai's profile drive the on/off decision.

    `openai_reasoning_summary` rides on the same profile-driven path: it is
    set iff `thinking` is, so we never send it to non-reasoning models or to
    custom OpenAI-compatible endpoints that wouldn't accept it.
    """
    config = AnyProviderConfig(api_key="test-key", base_url=base_url)
    provider: OpenAIProvider = (
        AzureOpenAIProvider(model_name, config)
        if provider_kind == "azure"
        else OpenAIProvider(model_name, config)
    )
    model = provider.create_model(max_tokens=512)
    settings = provider._build_agent_settings(model)

    has_thinking = settings is not None and settings.get("thinking") is True
    has_summary = (
        settings is not None and "openai_reasoning_summary" in settings
    )
    assert has_thinking == expected_thinking
    assert has_summary == expected_thinking


@pytest.mark.parametrize(
    (
        "model_name",
        "expected_model_settings",
        "expected_agent_thinking",
    ),
    [
        pytest.param(
            "claude-opus-4-7",
            # Opus 4.7 disallows sampling settings, so no temperature.
            {"max_tokens": 1024},
            True,
            id="opus_4_7_adaptive_no_sampling",
        ),
        pytest.param(
            "claude-opus-4-6",
            {"max_tokens": 1024, "temperature": 1},
            True,
            id="opus_4_6",
        ),
        pytest.param(
            "claude-sonnet-4-6",
            {"max_tokens": 1024, "temperature": 1},
            True,
            id="sonnet_4_6",
        ),
        pytest.param(
            "claude-opus-4-5-20251101",
            {"max_tokens": 1024, "temperature": 1},
            True,
            id="opus_4_5",
        ),
        pytest.param(
            "claude-3-7-sonnet-20250219",
            {"max_tokens": 1024, "temperature": 1},
            True,
            id="sonnet_3_7",
        ),
        # NOTE: pydantic-ai's profile reports `supports_thinking=True` for all
        # Anthropic models — even 3.5 — so by trusting it we end up enabling
        # thinking on 3.5 too. The Anthropic API will reject thinking for 3.5
        # at request time. We accept that trade-off in exchange for not
        # maintaining our own per-model gate; if pydantic-ai's profile gets
        # corrected upstream, behavior here will follow automatically.
        pytest.param(
            "claude-3-5-sonnet-20241022",
            {"max_tokens": 1024, "temperature": 1},
            True,
            id="sonnet_3_5_trusts_profile",
        ),
    ],
)
@pytest.mark.skipif(
    not DependencyManager.anthropic.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="anthropic or pydantic_ai not installed",
)
def test_anthropic_settings_split(
    model_name: str,
    expected_model_settings: dict[str, Any],
    expected_agent_thinking: bool,
) -> None:
    """Verify the model-level settings (temperature) and agent-level thinking flag."""
    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider(model_name, config)
    model = provider.create_model(max_tokens=1024)
    assert dict(model.settings) == expected_model_settings

    agent_settings = provider._build_agent_settings(model)
    actual_thinking = (
        agent_settings is not None and agent_settings.get("thinking") is True
    )
    assert actual_thinking == expected_agent_thinking


@pytest.mark.parametrize(
    ("model_name", "expected_payload_kind"),
    [
        # Adaptive-only / adaptive-supported models route to {'type': 'adaptive'}.
        pytest.param("claude-opus-4-7", "adaptive", id="opus_4_7_adaptive"),
        pytest.param("claude-opus-4-6", "adaptive", id="opus_4_6_adaptive"),
        pytest.param(
            "claude-sonnet-4-6", "adaptive", id="sonnet_4_6_adaptive"
        ),
        # Older models route to {'type': 'enabled', 'budget_tokens': N}.
        pytest.param(
            "claude-opus-4-5-20251101", "enabled", id="opus_4_5_manual"
        ),
        pytest.param(
            "claude-3-7-sonnet-20250219", "enabled", id="sonnet_3_7_manual"
        ),
    ],
)
@pytest.mark.skipif(
    not DependencyManager.anthropic.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="anthropic or pydantic_ai not installed",
)
def test_anthropic_thinking_payload_translation(
    model_name: str, expected_payload_kind: str
) -> None:
    """End-to-end: per-model Anthropic API payload via pydantic-ai's profile.

    Opus 4.7 is the critical case here: it only accepts `{"type": "adaptive"}`
    and rejects `{"type": "enabled", "budget_tokens": ...}` with HTTP 400.
    """
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.models.anthropic import AnthropicModel

    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider(model_name, config)
    model = provider.create_model(max_tokens=1024)
    assert isinstance(model, AnthropicModel)

    # Combine the model-level settings (temperature) with the agent-level
    # thinking flag the way pydantic-ai does at request time.
    merged = dict(model.settings or {})
    merged.update(provider._build_agent_settings(model) or {})

    prepared_settings, prepared_params = model.prepare_request(
        merged, ModelRequestParameters()
    )
    payload = model._translate_thinking(  # type: ignore[attr-defined]
        prepared_settings or {}, prepared_params
    )
    if expected_payload_kind == "adaptive":
        assert payload == {"type": "adaptive"}
    else:
        assert payload["type"] == "enabled"
        assert payload["budget_tokens"] > 0


@pytest.mark.parametrize(
    ("model_name", "expected_thinking"),
    [
        pytest.param("gemini-3-pro-preview", True, id="gemini_3_pro"),
        pytest.param("gemini-2.5-pro", True, id="gemini_2_5_pro"),
        pytest.param(
            "gemini-2.0-flash", False, id="gemini_2_0_flash_not_thinking"
        ),
    ],
)
@pytest.mark.skipif(
    not DependencyManager.google_ai.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="google or pydantic_ai not installed",
)
def test_google_default_thinking(
    model_name: str, expected_thinking: bool
) -> None:
    """Google's profile correctly distinguishes thinking vs non-thinking models."""
    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = GoogleProvider(model_name, config)
    model = provider.create_model(max_tokens=512)
    settings = provider._build_agent_settings(model)
    actual = settings is not None and settings.get("thinking") is True
    assert actual == expected_thinking


@pytest.mark.requires("pydantic_ai")
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
