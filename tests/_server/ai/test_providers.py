"""Tests for the LLM providers in marimo._server.ai.providers."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._config.config import AiConfig
from marimo._dependencies.dependencies import Dependency, DependencyManager
from marimo._server.ai.config import AnyProviderConfig
from marimo._server.ai.ids import AiModelId
from marimo._server.ai.providers import (
    AnthropicProvider,
    AzureOpenAIProvider,
    BedrockProvider,
    CustomProvider,
    GoogleProvider,
    OpenAIProvider,
    StreamOptions,
    _infer_provider_name_from_base_url,
    _normalize_base_url,
    get_completion_provider,
)
from marimo._server.ai.tracing import SpanInfo


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
        pytest.param("openrouter/openai/gpt-4", "openrouter", id="openrouter"),
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
            "openrouter/openai/gpt-4", CustomProvider, None, id="openrouter"
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
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=512)

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
            {"max_tokens": 1024, "anthropic_cache": True, "thinking": True},
            True,
            id="opus_4_7_adaptive_no_sampling",
        ),
        pytest.param(
            "claude-opus-4-6",
            {"max_tokens": 1024, "anthropic_cache": True, "thinking": True},
            True,
            id="opus_4_6",
        ),
        pytest.param(
            "claude-sonnet-4-6",
            {"max_tokens": 1024, "anthropic_cache": True, "thinking": True},
            True,
            id="sonnet_4_6",
        ),
        pytest.param(
            "claude-opus-4-5-20251101",
            {"max_tokens": 1024, "anthropic_cache": True, "thinking": True},
            True,
            id="opus_4_5",
        ),
        pytest.param(
            "claude-3-7-sonnet-20250219",
            {"max_tokens": 1024, "anthropic_cache": True, "thinking": True},
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
            {"max_tokens": 1024, "anthropic_cache": True, "thinking": True},
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
    """Verify request settings carry Anthropic max tokens/cache/thinking."""
    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider(model_name, config)
    model = provider.create_model()
    model_settings = provider._build_model_settings(model, max_tokens=1024)
    assert dict(model_settings) == expected_model_settings

    actual_thinking = (
        model_settings is not None and model_settings.get("thinking") is True
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
    from pydantic_ai.models.anthropic import (
        AnthropicModel,
        AnthropicModelSettings,
    )

    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider(model_name, config)
    model = provider.create_model()
    assert isinstance(model, AnthropicModel)

    settings = provider._build_model_settings(model, max_tokens=1024)
    prepared_settings, prepared_params = model.prepare_request(
        settings, ModelRequestParameters()
    )
    payload = model._translate_thinking(  # type: ignore[attr-defined]
        cast("AnthropicModelSettings", prepared_settings or {}),
        prepared_params,
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
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=512)
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
            span_info=SpanInfo(endpoint="completion", model="openai/gpt-4"),
        )

        mock_request.assert_called_once()
        request_messages = mock_request.call_args.args[0]

        assert len(request_messages) == 1
        # The bug caused instructions to be "Test prompt\nTest prompt"
        instructions = request_messages[0].instructions

        # This asserts the duplication is gone
        assert instructions == "Test prompt"


@pytest.mark.requires("pydantic_ai")
async def test_completion_tool_count_includes_capabilities() -> None:
    """`completion` reports tools plus the agent's native capabilities, so its
    telemetry matches the streaming paths."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)

    agent = MagicMock(name="agent")
    agent.root_capability.capabilities = [MagicMock(), MagicMock()]
    result = MagicMock()
    result.output = "hi"
    agent.run = AsyncMock(return_value=result)

    span_info = SpanInfo(endpoint="completion", model="openai/gpt-4")

    with patch.object(provider, "create_agent", return_value=agent):
        await provider.completion(
            messages=[],
            system_prompt="x",
            max_tokens=100,
            additional_tools=[MagicMock(name="tool")],
            span_info=span_info,
        )

    # 1 additional tool + 2 capabilities.
    assert span_info.tool_count == 3


@pytest.mark.skipif(
    not DependencyManager.anthropic.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="anthropic or pydantic_ai not installed",
)
def test_anthropic_applies_default_floor_when_max_tokens_none() -> None:
    """When no max_tokens is configured, Anthropic still receives 32768."""
    from marimo._server.ai.constants import ANTHROPIC_DEFAULT_MAX_TOKENS

    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider("claude-sonnet-4-5", config)
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=None)
    assert dict(settings).get("max_tokens") == ANTHROPIC_DEFAULT_MAX_TOKENS


@pytest.mark.skipif(
    not DependencyManager.anthropic.has()
    or not DependencyManager.pydantic_ai.has(),
    reason="anthropic or pydantic_ai not installed",
)
def test_anthropic_override_wins_over_default_floor() -> None:
    """An explicit max_tokens overrides the Anthropic default floor."""
    config = AnyProviderConfig(api_key="test-key", base_url=None)
    provider = AnthropicProvider("claude-sonnet-4-5", config)
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=12345)
    assert dict(settings).get("max_tokens") == 12345


@pytest.mark.requires("pydantic_ai")
def test_openai_chat_omits_max_tokens_when_none() -> None:
    """Non-Anthropic providers omit max_tokens entirely when not set, so
    pydantic-ai falls through to the upstream provider's default."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=None)
    assert "max_tokens" not in dict(settings or {})


@pytest.mark.requires("pydantic_ai")
def test_openai_chat_passes_explicit_max_tokens() -> None:
    """Non-Anthropic providers pass through an explicit max_tokens."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=12345)
    assert dict(settings or {}).get("max_tokens") == 12345


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_agent_passes_explicit_max_tokens() -> None:
    """Custom providers pass explicit max_tokens through agent settings."""
    config = AnyProviderConfig(
        api_key="test-key", base_url="https://my.internal.llm/v1"
    )
    provider = CustomProvider(
        AiModelId.from_model("my_provider/my-model"), config
    )
    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=12345)
    assert dict(settings).get("max_tokens") == 12345


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_agent_omits_max_tokens_when_none() -> None:
    """The chat path omits max_tokens from agent model_settings when unset."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = get_completion_provider(config, "openrouter/openai/gpt-4")
    with patch("marimo._server.ai.providers.get_tool_manager") as mock_get_tm:
        mock_get_tm.return_value = MagicMock()
        agent = provider.create_agent(
            name="test", max_tokens=None, tools=[], system_prompt="x"
        )
    settings = cast("dict[str, Any]", agent.model_settings or {})
    assert "max_tokens" not in settings


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param("", None, id="empty"),
        pytest.param(
            "https://api.deepseek.com", "api.deepseek.com", id="https"
        ),
        pytest.param(
            "http://api.deepseek.com/", "api.deepseek.com", id="http_trailing"
        ),
        pytest.param(
            "https://api.deepseek.com/v1/",
            "api.deepseek.com",
            id="strip_v1",
        ),
        pytest.param(
            "  https://API.DeepSeek.com/v1  ",
            "api.deepseek.com",
            id="whitespace_and_case",
        ),
        pytest.param(
            "https://openrouter.ai/api/v1",
            "openrouter.ai/api",
            id="path_before_v1",
        ),
        pytest.param(
            "https://models.github.ai/inference",
            "models.github.ai/inference",
            id="path_without_v1",
        ),
        pytest.param(
            "https://api.x.ai/V1",
            "api.x.ai",
            id="uppercase_v1_suffix",
        ),
        pytest.param(
            "https://generativelanguage.googleapis.com/v1beta",
            "generativelanguage.googleapis.com/v1beta",
            id="v1beta_not_stripped",
        ),
    ],
)
def test_normalize_base_url(
    base_url: str | None, expected: str | None
) -> None:
    assert _normalize_base_url(base_url) == expected


@pytest.mark.requires("pydantic_ai")
@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        pytest.param("https://api.deepseek.com", "deepseek", id="deepseek"),
        pytest.param(
            "https://api.deepseek.com/v1/", "deepseek", id="deepseek_v1"
        ),
        pytest.param(
            "https://api.moonshot.ai/v1", "moonshotai", id="moonshot"
        ),
        pytest.param(
            "https://openrouter.ai/api/v1/", "openrouter", id="openrouter"
        ),
        # Hosts not discovered from pydantic-ai's providers -> no match, so we
        # fall back to the generic OpenAI provider (preserving prior behavior).
        # `api.openai.com` is LiteLLM's client-derived default, which we skip.
        pytest.param("https://my.internal.llm/v1", None, id="unknown_host"),
        pytest.param("https://api.openai.com/v1", None, id="openai_host"),
        pytest.param(None, None, id="no_base_url"),
    ],
)
def test_infer_provider_name_from_base_url(
    base_url: str | None, expected: str | None
) -> None:
    assert _infer_provider_name_from_base_url(base_url) == expected


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_inherits_profile_from_base_url() -> None:
    """A custom provider whose name we don't recognize, but whose base URL
    points at DeepSeek, inherits DeepSeek's profile so `reasoning_content`
    round-trips. Regression test for #9786."""
    config = AnyProviderConfig(
        api_key="test-key", base_url="https://api.deepseek.com"
    )
    provider = CustomProvider(
        AiModelId.from_model("deepseek_official/deepseek-v4-flash"), config
    )

    # The unknown name was resolved to the known `deepseek` provider.
    assert provider._provider_name == "deepseek"
    assert provider.provider.name == "deepseek"

    model = provider.create_model()
    profile = model.profile
    if isinstance(profile, dict):
        assert profile.get("openai_chat_thinking_field") == "reasoning_content"
        assert profile.get("openai_chat_send_back_thinking_parts") == "field"
    else:
        assert profile.openai_chat_thinking_field == "reasoning_content"
        assert profile.openai_chat_send_back_thinking_parts == "field"


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_unknown_base_url_stays_generic() -> None:
    """An unknown name with an unrecognized base URL falls back to the generic
    OpenAI provider (no thinking field), preserving prior behavior."""
    config = AnyProviderConfig(
        api_key="test-key", base_url="https://my.internal.llm/v1"
    )
    provider = CustomProvider(
        AiModelId.from_model("my_provider/my-model"), config
    )

    assert provider._provider_name == "my_provider"
    assert provider.provider.name == "openai"

    model = provider.create_model()
    profile = model.profile
    if isinstance(profile, dict):
        assert profile.get("openai_chat_thinking_field") is None
    else:
        assert profile.openai_chat_thinking_field is None


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_create_model_infers_from_registry() -> None:
    """`create_model` resolves the model through pydantic-ai's registry using
    the `provider:model` id so we get the provider-tuned model class."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = get_completion_provider(config, "openrouter/openai/gpt-4")
    assert isinstance(provider, CustomProvider)

    sentinel = MagicMock(name="inferred-model")
    with patch(
        "pydantic_ai.models.infer_model", return_value=sentinel
    ) as mock_infer:
        model = provider.create_model()

    assert model is sentinel
    assert mock_infer.call_args.args[0] == "openrouter:openai/gpt-4"


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_known_name_not_overridden_by_base_url() -> None:
    """A recognized provider name is used as-is; the base URL never overrides
    it (so e.g. an OpenRouter config pointed at DeepSeek keeps OpenRouter)."""
    config = AnyProviderConfig(
        api_key="test-key", base_url="https://api.deepseek.com"
    )
    provider = CustomProvider(
        AiModelId.from_model("openrouter/some-model"), config
    )
    assert provider._provider_name == "openrouter"


@pytest.mark.requires("pydantic_ai")
async def test_stream_completion_harness_wires_execute_code_toolset() -> None:
    """The code-mode harness builds an agent with the execute_code toolset,
    passes the system prompt as instructions, and returns the adapter's
    streaming response."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)

    session = MagicMock(name="session")
    request = MagicMock(name="request")
    toolset = MagicMock(name="toolset")
    streaming_response = MagicMock(name="streaming_response")
    adapter: MagicMock = MagicMock(name="adapter")
    adapter.streaming_response = MagicMock(return_value=streaming_response)
    stream_options = StreamOptions(
        span_info=SpanInfo(endpoint="chat", model="openai/gpt-4"),
    )

    def build_mock_agent(*_args: Any, **kwargs: Any) -> MagicMock:
        # `tool_count` reads back the agent's aggregated capabilities, so the
        # mock must expose the capabilities it was constructed with.
        agent = MagicMock(name="agent")
        agent.root_capability.capabilities = kwargs.get("capabilities", [])
        return agent

    with (
        patch.object(provider, "create_model", return_value=MagicMock()),
        patch.object(provider, "_build_model_settings", return_value={}),
        # Isolate from provider-adaptive web tools (covered separately) so the
        # only capabilities are the three references capabilities.
        patch.object(provider, "_build_agent_capabilities", return_value=[]),
        patch.object(provider, "convert_messages", return_value=[]),
        patch(
            "marimo._server.ai.tools.code_mode.build_execute_code_toolset",
            return_value=toolset,
        ) as mock_build_toolset,
        patch("pydantic_ai.Agent", side_effect=build_mock_agent) as mock_agent,
        patch(
            "pydantic_ai.ui.vercel_ai.VercelAIAdapter",
            return_value=adapter,
        ),
    ):
        result = await provider.stream_completion_harness(
            messages=[],
            system_prompt="SYSTEM PROMPT WITH SKILL",
            session=session,
            request=request,
            max_tokens=1234,
            stream_options=stream_options,
        )

    assert result is streaming_response
    assert stream_options.span_info.tool_count == 4
    # The toolset is bound to the caller's session and request.
    mock_build_toolset.assert_called_once_with(session, request)

    # The agent is constructed with that toolset and the system prompt as
    # instructions (which now carries the marimo-pair skill).
    agent_kwargs = mock_agent.call_args.kwargs
    assert agent_kwargs["toolsets"] == [toolset]
    assert agent_kwargs["instructions"] == "SYSTEM PROMPT WITH SKILL"
    capabilities = agent_kwargs["capabilities"]
    assert len(capabilities) == 3
    assert {capability.id for capability in capabilities} == {
        "gotchas",
        "notebook-improvements",
        "rich-representations",
    }
    assert all(capability.defer_loading for capability in capabilities)


@pytest.mark.requires("pydantic_ai")
def test_create_custom_provider_passes_supported_credentials() -> None:
    """`_create_custom_provider` constructs the resolved provider class,
    passing only the credentials its constructor accepts."""
    config = AnyProviderConfig(api_key="test-key", base_url="https://x/v1")
    provider = get_completion_provider(config, "openrouter/openai/gpt-4")
    assert isinstance(provider, CustomProvider)

    captured: dict[str, Any] = {}

    class FakeProvider:
        def __init__(
            self, *, api_key: str | None = None, base_url: str | None = None
        ) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url

    result = provider._create_custom_provider(FakeProvider, config)  # type: ignore[arg-type]
    assert isinstance(result, FakeProvider)
    assert captured == {"api_key": "test-key", "base_url": "https://x/v1"}


@pytest.mark.requires("pydantic_ai")
def test_create_custom_provider_omits_unsupported_base_url() -> None:
    """A provider whose constructor has no `base_url` parameter is built with
    just the api key, even when the config carries a base URL."""
    config = AnyProviderConfig(api_key="test-key", base_url="https://x/v1")
    provider = get_completion_provider(config, "openrouter/openai/gpt-4")
    assert isinstance(provider, CustomProvider)

    captured: dict[str, Any] = {}

    class ApiKeyOnlyProvider:
        def __init__(self, *, api_key: str | None = None) -> None:
            captured["api_key"] = api_key

    result = provider._create_custom_provider(ApiKeyOnlyProvider, config)  # type: ignore[arg-type]
    assert isinstance(result, ApiKeyOnlyProvider)
    assert captured == {"api_key": "test-key"}


@pytest.mark.requires("pydantic_ai")
def test_create_custom_provider_falls_back_to_openai_on_error() -> None:
    """If constructing the provider raises, we fall back to a generic
    OpenAI-compatible provider rather than propagating the error."""
    from pydantic_ai.providers.openai import (
        OpenAIProvider as PydanticOpenAI,
    )

    config = AnyProviderConfig(api_key="test-key", base_url="https://x/v1")
    provider = get_completion_provider(config, "openrouter/openai/gpt-4")
    assert isinstance(provider, CustomProvider)

    class BrokenProvider:
        def __init__(self, *, api_key: str | None = None) -> None:
            del api_key
            raise RuntimeError("boom")

    result = provider._create_custom_provider(BrokenProvider, config)  # type: ignore[arg-type]
    assert isinstance(result, PydanticOpenAI)


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_applies_openrouter_cache_settings() -> None:
    """OpenRouter agents opt into prompt caching at the agent-settings level."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = get_completion_provider(config, "openrouter/openai/gpt-4")
    assert isinstance(provider, CustomProvider)

    model = provider.create_model()
    settings = cast(
        "dict[str, Any]",
        provider._build_model_settings(model, max_tokens=100),
    )

    assert settings["openrouter_cache_instructions"] is True
    assert settings["openrouter_cache_messages"] is True
    assert settings["openrouter_cache_tool_definitions"] == "1h"


@pytest.mark.requires("pydantic_ai")
def test_custom_provider_non_openrouter_omits_cache_settings() -> None:
    """Non-OpenRouter custom providers don't get OpenRouter-specific settings."""
    config = AnyProviderConfig(
        api_key="test-key", base_url="https://my.internal.llm/v1"
    )
    provider = CustomProvider(
        AiModelId.from_model("my_provider/my-model"), config
    )

    model = provider.create_model()
    settings = provider._build_model_settings(model, max_tokens=None)

    assert "openrouter_cache_instructions" not in settings
    assert "max_tokens" not in settings


@pytest.mark.requires("pydantic_ai")
def test_build_agent_capabilities_from_native_tool_support() -> None:
    """Provider-adaptive tools are enabled based on the model profile's
    supported native tools when no local search/fetch deps are installed."""
    from pydantic_ai.native_tools import (
        WebFetchTool,
        WebSearchTool,
        XSearchTool,
    )

    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)

    model = MagicMock(name="model")
    model.profile.supported_native_tools = {
        WebSearchTool,
        WebFetchTool,
        XSearchTool,
    }

    with (
        patch.object(
            DependencyManager.duckduckgo_search, "has", return_value=False
        ),
        patch.object(DependencyManager.markdownify, "has", return_value=False),
    ):
        capabilities = provider._build_agent_capabilities(model)

    assert sorted(type(c).__name__ for c in capabilities) == [
        "WebFetch",
        "WebSearch",
        "XSearch",
    ]


@pytest.mark.requires("pydantic_ai")
def test_build_agent_capabilities_empty_without_support_or_deps() -> None:
    """No capabilities are added when the model supports no native tools and
    no local search/fetch deps are installed."""
    config = AnyProviderConfig(api_key="test-key", base_url="http://test-url")
    provider = OpenAIProvider("gpt-4", config)

    model = MagicMock(name="model")
    model.profile.supported_native_tools = set()

    with (
        patch.object(
            DependencyManager.duckduckgo_search, "has", return_value=False
        ),
        patch.object(DependencyManager.markdownify, "has", return_value=False),
    ):
        capabilities = provider._build_agent_capabilities(model)

    assert capabilities == []
