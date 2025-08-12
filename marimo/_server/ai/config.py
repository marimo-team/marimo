# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any,
    Optional,
    Union,
    cast,
)

from starlette.exceptions import HTTPException

from marimo._config.config import (
    AiConfig,
    CopilotMode,
    MarimoConfig,
    PartialMarimoConfig,
)
from marimo._server.ai.constants import DEFAULT_MAX_TOKENS, DEFAULT_MODEL
from marimo._server.ai.ids import AiModelId
from marimo._server.ai.tools import Tool, get_tool_manager
from marimo._server.api.status import HTTPStatus


@dataclass
class AnyProviderConfig:
    """Normalized config for any AI provider."""

    base_url: Optional[str]
    api_key: str
    ssl_verify: Optional[bool] = None
    ca_bundle_path: Optional[str] = None
    client_pem: Optional[str] = None
    tools: list[Tool] = field(default_factory=list)

    @classmethod
    def for_openai(cls, config: AiConfig) -> AnyProviderConfig:
        fallback_key = cls.os_key("OPENAI_API_KEY")
        return cls._for_openai_like(
            config, "open_ai", "OpenAI", fallback_key=fallback_key
        )

    @classmethod
    def for_azure(cls, config: AiConfig) -> AnyProviderConfig:
        fallback_key = cls.os_key("AZURE_API_KEY")
        return cls._for_openai_like(
            config, "azure", "Azure OpenAI", fallback_key=fallback_key
        )

    @classmethod
    def for_openai_compatible(cls, config: AiConfig) -> AnyProviderConfig:
        return cls._for_openai_like(
            config, "open_ai_compatible", "OpenAI Compatible"
        )

    @classmethod
    def for_ollama(cls, config: AiConfig) -> AnyProviderConfig:
        return cls._for_openai_like(
            config, "ollama", "Ollama", fallback_key="ollama-placeholder"
        )

    @classmethod
    def _for_openai_like(
        cls,
        config: AiConfig,
        key: str,
        name: str,
        *,
        fallback_key: Optional[str] = None,
    ) -> AnyProviderConfig:
        ai_config = _get_ai_config(config, key, name)
        key = _get_key(ai_config, name, fallback_key=fallback_key)

        kwargs: dict[str, Any] = {
            "base_url": _get_base_url(ai_config),
            "api_key": key,
            "ssl_verify": ai_config.get("ssl_verify", True),
            "ca_bundle_path": ai_config.get("ca_bundle_path", None),
            "client_pem": ai_config.get("client_pem", None),
        }

        # Only include tools if they are available
        # Empty tools list causes an error with deepseek
        # https://discord.com/channels/1059888774789730424/1387766267792068821
        tools = _get_tools(config.get("mode", "manual"))
        if len(tools) > 0:
            kwargs["tools"] = tools

        return AnyProviderConfig(**kwargs)

    @classmethod
    def for_anthropic(cls, config: AiConfig) -> AnyProviderConfig:
        ai_config = _get_ai_config(config, "anthropic", "Anthropic")
        key = _get_key(
            ai_config,
            "Anthropic",
            fallback_key=cls.os_key("ANTHROPIC_API_KEY"),
        )
        return cls(
            base_url=_get_base_url(ai_config),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @classmethod
    def for_google(cls, config: AiConfig) -> AnyProviderConfig:
        fallback_key = cls.os_key("GEMINI_API_KEY") or cls.os_key(
            "GOOGLE_API_KEY"
        )
        ai_config = _get_ai_config(config, "google", "Google AI")
        key = _get_key(
            ai_config,
            "Google AI",
            fallback_key=fallback_key,
        )
        return cls(
            base_url=_get_base_url(ai_config),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @classmethod
    def for_bedrock(cls, config: AiConfig) -> AnyProviderConfig:
        ai_config = _get_ai_config(config, "bedrock", "Bedrock")
        key = _get_key(ai_config, "Bedrock")
        return cls(
            base_url=_get_base_url(ai_config),
            api_key=key,
            tools=_get_tools(config.get("mode", "manual")),
        )

    @classmethod
    def for_model(cls, model: str, config: AiConfig) -> AnyProviderConfig:
        model_id = AiModelId.from_model(model)
        if model_id.provider == "anthropic":
            return cls.for_anthropic(config)
        elif model_id.provider == "google":
            return cls.for_google(config)
        elif model_id.provider == "bedrock":
            return cls.for_bedrock(config)
        elif model_id.provider == "ollama":
            return cls.for_ollama(config)
        elif model_id.provider == "openai":
            return cls.for_openai(config)
        elif model_id.provider == "azure":
            return cls.for_azure(config)
        elif model_id.provider == "openai_compatible":
            return cls.for_openai_compatible(config)
        else:
            # Catch-all: try OpenAI compatible first, then OpenAI.
            try:
                return cls.for_openai_compatible(config)
            except HTTPException:
                return cls.for_openai(config)

    @classmethod
    def os_key(cls, key: str) -> Optional[str]:
        import os

        return os.environ.get(key)


def _get_tools(mode: CopilotMode) -> list[Tool]:
    tool_manager = get_tool_manager()
    return tool_manager.get_tools_for_mode(mode)


def _get_ai_config(config: AiConfig, key: str, name: str) -> dict[str, Any]:
    if key not in config:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{name} config not found",
        )
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
    config: Union[MarimoConfig, PartialMarimoConfig],
) -> str:
    """Get the autocomplete model from the config."""
    return (
        # Current config
        config.get("ai", {}).get("models", {}).get("autocomplete_model")
        # Legacy config
        or config.get("completion", {}).get("model")
        or DEFAULT_MODEL
    )


def get_max_tokens(config: MarimoConfig) -> int:
    if "ai" not in config:
        return DEFAULT_MAX_TOKENS
    if "max_tokens" not in config["ai"]:
        return DEFAULT_MAX_TOKENS
    return config["ai"]["max_tokens"]


def _get_key(
    config: Any,
    name: str,
    *,
    fallback_key: Optional[str] = None,
) -> str:
    """Get the API key for a given provider."""
    if not isinstance(config, dict):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid config",
        )

    config = cast(dict[str, Any], config)

    if name == "Bedrock":
        if "profile_name" in config:
            profile_name = config.get("profile_name", "")
            return f"profile:{profile_name}"
        elif (
            "aws_access_key_id" in config and "aws_secret_access_key" in config
        ):
            return f"{config['aws_access_key_id']}:{config['aws_secret_access_key']}"
        else:
            return ""

    if "api_key" in config:
        key = config["api_key"]
        if key:
            return cast(str, key)

    if "http://127.0.0.1:11434/" in config.get("base_url", ""):
        # Ollama can be configured and in that case the api key is not needed.
        # We send a placeholder value to prevent the user from being confused.
        return "ollama-placeholder"

    if fallback_key:
        return fallback_key

    raise HTTPException(
        status_code=HTTPStatus.BAD_REQUEST,
        detail=f"{name} API key not configured",
    )


def _get_base_url(config: Any, name: str = "") -> Optional[str]:
    """Get the base URL for a given provider."""
    if not isinstance(config, dict):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invalid config",
        )

    if name == "Bedrock":
        if "region_name" in config:
            return cast(str, config["region_name"])
        else:
            return None
    elif "base_url" in config:
        return cast(str, config["base_url"])
    return None
