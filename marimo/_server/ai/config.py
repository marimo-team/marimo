# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import (
    Any,
    cast,
)

from starlette.exceptions import HTTPException

from marimo._config.config import (
    AiConfig,
    CopilotMode,
    MarimoConfig,
    PartialMarimoConfig,
)
from marimo._server.ai.constants import DEFAULT_MODEL
from marimo._server.ai.ids import AiModelId
from marimo._server.ai.tools.tool_manager import get_tool_manager
from marimo._server.ai.tools.types import ToolDefinition
from marimo._utils.http import HTTPStatus

# https://github.com/pydantic/pydantic-ai/blob/8b9ac2bde2355b0d431abea6cf210a36fffe0c43/pydantic_ai_slim/pydantic_ai/providers/github.py#L41C17-L41C51
GITHUB_COPILOT_BASE_URL = "https://models.github.ai/inference"
ENV_SECRET_PREFIX = "env:"

SecretResolver = Callable[[str], str | None]


@dataclass
class AnyProviderConfig:
    """Normalized config for any AI provider."""

    base_url: str | None
    api_key: str
    project: str | None = None
    ssl_verify: bool | None = None
    ca_bundle_path: str | None = None
    client_pem: str | None = None
    extra_headers: dict[str, str] | None = None
    tools: list[ToolDefinition] | None = None

    def __post_init__(self) -> None:
        # Only include tools if they are available
        # Empty tools list causes an error with deepseek
        # https://discord.com/channels/1059888774789730424/1387766267792068821
        if not self.tools:
            self.tools = None

    @classmethod
    def for_openai(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret("OPENAI_API_KEY", secret_resolver)
        return cls._for_openai_like(
            config,
            "open_ai",
            "OpenAI",
            fallback_key=fallback_key,
            require_key=True,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_azure(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret("AZURE_API_KEY", secret_resolver)
        return cls._for_openai_like(
            config,
            "azure",
            "Azure OpenAI",
            fallback_key=fallback_key,
            require_key=True,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_openai_compatible(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        return cls._for_openai_like(
            config,
            "open_ai_compatible",
            "OpenAI Compatible",
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_custom_provider(
        cls,
        config: AiConfig,
        provider_name: str,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        """Get config for a custom provider by name."""
        custom_providers = cast(
            dict[str, Any], config.get("custom_providers", {})
        )
        if provider_name not in custom_providers:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Custom provider '{provider_name}' not configured. "
                "Go to Settings > AI to configure.",
            )

        provider_config = cast(dict[str, Any], custom_providers[provider_name])
        return cls._for_openai_like(
            config,
            key=provider_name,
            name=provider_name.replace("_", " ").title(),
            require_key=False,
            ai_config=provider_config,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_ollama(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        default_base_url = "http://127.0.0.1:11434/v1"
        return cls._for_openai_like(
            config,
            "ollama",
            "Ollama",
            fallback_key="ollama-placeholder",
            fallback_base_url=default_base_url,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_github(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret("GITHUB_TOKEN", secret_resolver)
        result = cls._for_openai_like(
            config,
            "github",
            "GitHub",
            fallback_key=fallback_key,
            # Default base URL for GitHub Copilot, taken from
            fallback_base_url=GITHUB_COPILOT_BASE_URL,
            require_key=True,
            secret_resolver=secret_resolver,
        )

        # Add default extra headers for GitHub, but allow user to override
        default_headers = {
            "editor-version": "vscode/1.95.0",
            "Copilot-Integration-Id": "vscode-chat",
        }

        # Merge: user headers override defaults
        if result.extra_headers:
            merged_headers = {**default_headers, **result.extra_headers}
        else:
            merged_headers = default_headers

        result.extra_headers = merged_headers
        return result

    @classmethod
    def for_openrouter(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret(
            "OPENROUTER_API_KEY", secret_resolver
        )
        return cls._for_openai_like(
            config,
            "openrouter",
            "OpenRouter",
            fallback_key=fallback_key,
            # Default base URL for OpenRouter
            fallback_base_url="https://openrouter.ai/api/v1/",
            require_key=True,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_wandb(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret("WANDB_API_KEY", secret_resolver)
        return cls._for_openai_like(
            config,
            "wandb",
            "Weights & Biases",
            fallback_key=fallback_key,
            # Default base URL for Weights & Biases
            fallback_base_url="https://api.inference.wandb.ai/v1/",
            require_key=True,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def for_opencode_go(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret("OPENCODE_API_KEY", secret_resolver)
        return cls._for_openai_like(
            config,
            "opencode_go",
            "OpenCode Go",
            fallback_key=fallback_key,
            # Default base URL for OpenCode Go
            fallback_base_url="https://opencode.ai/zen/go/v1/",
            require_key=True,
            secret_resolver=secret_resolver,
        )

    @classmethod
    def _for_openai_like(
        cls,
        config: AiConfig,
        key: str,
        name: str,
        *,
        fallback_key: str | None = None,
        fallback_base_url: str | None = None,
        require_key: bool = False,
        ai_config: dict[str, Any] | None = None,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        ai_config = ai_config or _get_ai_config(config, key)
        key = _get_key(
            ai_config,
            name,
            fallback_key=fallback_key,
            require_key=require_key,
            secret_resolver=secret_resolver,
        )

        # Use SSL_CERT_FILE environment variable as fallback for ca_bundle_path
        ca_bundle_path = ai_config.get("ca_bundle_path") or cls.os_key(
            "SSL_CERT_FILE"
        )

        kwargs: dict[str, Any] = {
            "base_url": _get_base_url(ai_config) or fallback_base_url,
            "api_key": key,
            "project": ai_config.get("project", None),
            "ssl_verify": ai_config.get("ssl_verify", True),
            "ca_bundle_path": ca_bundle_path,
            "client_pem": ai_config.get("client_pem", None),
            "extra_headers": ai_config.get("extra_headers", None),
            "tools": _get_tools(config.get("mode", "manual")),
        }

        return AnyProviderConfig(**kwargs)

    @classmethod
    def for_anthropic(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        ai_config = _get_ai_config(config, "anthropic")
        fallback_key = cls._resolve_secret(
            "ANTHROPIC_API_KEY", secret_resolver
        )
        key = _get_key(
            ai_config,
            "Anthropic",
            fallback_key=fallback_key,
            require_key=True,
            secret_resolver=secret_resolver,
        )
        return cls(
            base_url=_get_base_url(ai_config),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @classmethod
    def for_google(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        fallback_key = cls._resolve_secret(
            "GEMINI_API_KEY", secret_resolver
        ) or cls._resolve_secret("GOOGLE_API_KEY", secret_resolver)
        ai_config = _get_ai_config(config, "google")
        key = _get_key(
            ai_config,
            "Google AI",
            fallback_key=fallback_key,
            require_key=False,
            secret_resolver=secret_resolver,
        )
        return cls(
            base_url=_get_base_url(ai_config),
            api_key=key,
            ssl_verify=True,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @classmethod
    def for_bedrock(
        cls,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        ai_config = _get_ai_config(config, "bedrock")
        key = _get_key(ai_config, "Bedrock", secret_resolver=secret_resolver)
        return cls(
            base_url=_get_base_url(ai_config, "Bedrock"),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @classmethod
    def for_model(
        cls,
        model: str,
        config: AiConfig,
        *,
        secret_resolver: SecretResolver | None = None,
    ) -> AnyProviderConfig:
        model_id = AiModelId.from_model(model)
        if model_id.provider == "anthropic":
            return cls.for_anthropic(config, secret_resolver=secret_resolver)
        elif model_id.provider == "google":
            return cls.for_google(config, secret_resolver=secret_resolver)
        elif model_id.provider == "bedrock":
            return cls.for_bedrock(config, secret_resolver=secret_resolver)
        elif model_id.provider == "ollama":
            return cls.for_ollama(config, secret_resolver=secret_resolver)
        elif model_id.provider == "openai":
            return cls.for_openai(config, secret_resolver=secret_resolver)
        elif model_id.provider == "azure":
            return cls.for_azure(config, secret_resolver=secret_resolver)
        elif model_id.provider == "github":
            return cls.for_github(config, secret_resolver=secret_resolver)
        elif model_id.provider == "openrouter":
            return cls.for_openrouter(config, secret_resolver=secret_resolver)
        elif model_id.provider == "wandb":
            return cls.for_wandb(config, secret_resolver=secret_resolver)
        elif model_id.provider == "opencode-go":
            return cls.for_opencode_go(config, secret_resolver=secret_resolver)
        elif model_id.provider == "openai_compatible":
            return cls.for_openai_compatible(
                config, secret_resolver=secret_resolver
            )
        else:
            custom_providers = cast(
                dict[str, Any], config.get("custom_providers", {})
            )
            if model_id.provider in custom_providers:
                return cls.for_custom_provider(
                    config,
                    model_id.provider,
                    secret_resolver=secret_resolver,
                )

            # Catch-all: use OpenAI compatible when it is configured.
            if "open_ai_compatible" in config:
                return cls.for_openai_compatible(
                    config, secret_resolver=secret_resolver
                )
            return cls.for_openai(config, secret_resolver=secret_resolver)

    @classmethod
    def _resolve_secret(
        cls, key: str, secret_resolver: SecretResolver | None
    ) -> str | None:
        if secret_resolver is not None:
            return secret_resolver(key)
        return cls.os_key(key)

    @classmethod
    def os_key(cls, key: str) -> str | None:
        import os

        return os.environ.get(key)


def _get_tools(mode: CopilotMode) -> list[ToolDefinition]:
    try:
        tool_manager = get_tool_manager()
    except ValueError:
        # ToolManager may not be initialized in some tests or non-server contexts
        return []
    return tool_manager.get_tools_for_mode(mode)


def _get_ai_config(config: AiConfig, key: str) -> dict[str, Any]:
    if key not in config:
        return {}
    return cast(dict[str, Any], config.get(key, {}))


def get_chat_model(config: AiConfig) -> str:
    """Get the chat model from the config."""
    return (
        # Current config
        config.get("models", {}).get("chat_model")
        # Legacy config
        or config.get("open_ai", {}).get("model")
        or DEFAULT_MODEL
    )


def get_edit_model(config: AiConfig) -> str:
    """Get the edit model from the config."""
    return config.get("models", {}).get("edit_model") or get_chat_model(config)


def get_autocomplete_model(
    config: MarimoConfig | PartialMarimoConfig,
) -> str:
    """Get the autocomplete model from the config."""
    return (
        # Current config
        config.get("ai", {}).get("models", {}).get("autocomplete_model")
        # Legacy config
        or config.get("completion", {}).get("model")
        or DEFAULT_MODEL
    )


def get_max_tokens(config: MarimoConfig) -> int | None:
    if "ai" not in config or "max_tokens" not in config["ai"]:
        return None
    return config["ai"]["max_tokens"]


def _get_key(
    config: Any,
    name: str,
    *,
    fallback_key: str | None = None,
    require_key: bool = False,
    secret_resolver: SecretResolver | None = None,
) -> str:
    """Get the API key for a given provider."""
    if not isinstance(config, dict):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid config for {name}. Go to Settings > AI to configure.",
        )

    config = cast(dict[str, Any], config)

    if name == "Bedrock":
        return _get_bedrock_key(config, secret_resolver=secret_resolver)

    if "api_key" in config:
        key = config["api_key"]
        if key:
            return _resolve_environment_reference(
                cast(str, key),
                name=f"{name} API key",
                secret_resolver=secret_resolver,
            )

    if "http://127.0.0.1:11434/" in config.get("base_url", ""):
        # Ollama can be configured and in that case the api key is not needed.
        # We send a placeholder value to prevent the user from being confused.
        return "ollama-placeholder"

    if fallback_key:
        return fallback_key

    if require_key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{name} API key not configured. Go to Settings > AI to configure.",
        )

    return ""


def _get_bedrock_key(
    config: dict[str, Any],
    *,
    secret_resolver: SecretResolver | None,
) -> str:
    profile_name = config.get("profile_name")
    if profile_name:
        return f"profile:{profile_name}"

    access_key_id = config.get("aws_access_key_id")
    secret_access_key = config.get("aws_secret_access_key")
    if not access_key_id and not secret_access_key:
        # Let the AWS SDK use its default credential chain.
        return ""
    if not access_key_id or not secret_access_key:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                "Bedrock AWS access key ID and secret access key "
                "must be configured together."
            ),
        )

    resolved_access_key_id = _resolve_environment_reference(
        cast(str, access_key_id),
        name="Bedrock AWS access key ID",
        secret_resolver=secret_resolver,
    )
    resolved_secret_access_key = _resolve_environment_reference(
        cast(str, secret_access_key),
        name="Bedrock AWS secret access key",
        secret_resolver=secret_resolver,
    )
    return f"{resolved_access_key_id}:{resolved_secret_access_key}"


def _resolve_environment_reference(
    value: str,
    *,
    name: str,
    secret_resolver: SecretResolver | None,
) -> str:
    if not value.startswith(ENV_SECRET_PREFIX):
        return value

    secret_name = value.removeprefix(ENV_SECRET_PREFIX)
    if not secret_name:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{name} has an empty environment variable reference.",
        )

    resolved_value = AnyProviderConfig._resolve_secret(
        secret_name, secret_resolver
    )
    if not resolved_value:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{name} environment variable '{secret_name}' is not set.",
        )
    return resolved_value


def _get_base_url(config: Any, name: str = "") -> str | None:
    """Get the base URL for a given provider."""
    if not isinstance(config, dict):
        if name:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"{name} is not configured. Go to Settings > AI to configure.",
            )
        else:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Invalid config. Go to Settings > AI to configure.",
            )

    if name == "Bedrock":
        if "region_name" in config:
            return cast(str, config["region_name"])
        else:
            return None
    elif "base_url" in config:
        return cast(str, config["base_url"])
    return None
