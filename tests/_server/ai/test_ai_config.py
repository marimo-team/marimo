# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Any, cast
from unittest.mock import patch

import pytest
from starlette.exceptions import HTTPException

from marimo._config.config import (
    AiConfig,
    MarimoConfig,
)
from marimo._server.ai.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    AnyProviderConfig,
    _get_ai_config,
    _get_base_url,
    _get_key,
    get_autocomplete_model,
    get_chat_model,
    get_edit_model,
    get_max_tokens,
)
from marimo._server.ai.tools import Tool
from marimo._server.api.status import HTTPStatus


class TestAnyProviderConfig:
    """Tests for AnyProviderConfig class."""

    def test_for_openai_basic(self):
        """Test basic OpenAI configuration."""
        config: AiConfig = {
            "open_ai": {
                "api_key": "test-openai-key",
                "model": "gpt-4",
            }
        }

        provider_config = AnyProviderConfig.for_openai(config)

        assert provider_config.api_key == "test-openai-key"
        assert provider_config.base_url is None
        assert provider_config.ssl_verify is True
        assert provider_config.ca_bundle_path is None
        assert provider_config.client_pem is None

    def test_for_openai_with_base_url(self):
        """Test OpenAI configuration with custom base URL."""
        config: AiConfig = {
            "open_ai": {
                "api_key": "test-key",
                "base_url": "https://custom.openai.com",
                "ssl_verify": False,
                "ca_bundle_path": "/path/to/ca.pem",
                "client_pem": "/path/to/client.pem",
            }
        }

        provider_config = AnyProviderConfig.for_openai(config)

        assert provider_config.api_key == "test-key"
        assert provider_config.base_url == "https://custom.openai.com"
        assert provider_config.ssl_verify is False
        assert provider_config.ca_bundle_path == "/path/to/ca.pem"
        assert provider_config.client_pem == "/path/to/client.pem"

    def test_for_azure(self):
        """Test Azure OpenAI configuration."""
        config: AiConfig = {
            "azure": {
                "api_key": "test-azure-key",
                "base_url": "https://test.openai.azure.com",
            }
        }

        provider_config = AnyProviderConfig.for_azure(config)

        assert provider_config.api_key == "test-azure-key"
        assert provider_config.base_url == "https://test.openai.azure.com"

    def test_for_openai_compatible(self):
        """Test OpenAI compatible service configuration."""
        config: AiConfig = {
            "open_ai_compatible": {
                "api_key": "test-compatible-key",
                "base_url": "https://compatible.service.com",
            }
        }

        provider_config = AnyProviderConfig.for_openai_compatible(config)

        assert provider_config.api_key == "test-compatible-key"
        assert provider_config.base_url == "https://compatible.service.com"

    def test_for_ollama(self):
        """Test Ollama configuration."""
        config: AiConfig = {
            "ollama": {
                "api_key": "test-ollama-key",
                "base_url": "http://localhost:11434",
            }
        }

        provider_config = AnyProviderConfig.for_ollama(config)

        assert provider_config.api_key == "test-ollama-key"
        assert provider_config.base_url == "http://localhost:11434"

    def test_for_ollama_placeholder_key(self):
        """Test Ollama configuration with default URL gets placeholder key."""
        config: AiConfig = {
            "ollama": {
                "base_url": "http://127.0.0.1:11434/",
            }
        }

        provider_config = AnyProviderConfig.for_ollama(config)

        assert provider_config.api_key == "ollama-placeholder"

    def test_for_anthropic(self):
        """Test Anthropic configuration."""
        config: AiConfig = {
            "anthropic": {
                "api_key": "test-anthropic-key",
            }
        }

        provider_config = AnyProviderConfig.for_anthropic(config)

        assert provider_config.api_key == "test-anthropic-key"
        assert provider_config.base_url is None

    def test_for_google(self):
        """Test Google AI configuration."""
        config: AiConfig = {
            "google": {
                "api_key": "test-google-key",
            }
        }

        provider_config = AnyProviderConfig.for_google(config)

        assert provider_config.api_key == "test-google-key"
        assert provider_config.base_url is None

    def test_for_bedrock_with_profile(self):
        """Test Bedrock configuration with profile name."""
        config: AiConfig = {
            "bedrock": {
                "profile_name": "test-profile",
                "region_name": "us-east-1",
            }
        }

        provider_config = AnyProviderConfig.for_bedrock(config)

        assert provider_config.api_key == "profile:test-profile"
        # Note: base_url is None because _get_base_url doesn't get "Bedrock" name parameter
        assert provider_config.base_url is None

    def test_for_bedrock_with_credentials(self):
        """Test Bedrock configuration with AWS credentials."""
        config: AiConfig = {
            "bedrock": {
                "aws_access_key_id": "test-access-key",
                "aws_secret_access_key": "test-secret-key",
                "region_name": "us-west-2",
            }
        }

        provider_config = AnyProviderConfig.for_bedrock(config)

        assert provider_config.api_key == "test-access-key:test-secret-key"
        # Note: base_url is None because _get_base_url doesn't get "Bedrock" name parameter
        assert provider_config.base_url is None

    def test_for_model_openai(self) -> None:
        """Test for_model with OpenAI model."""
        config: AiConfig = {"open_ai": {"api_key": "test-key"}}

        provider_config = AnyProviderConfig.for_model("gpt-4", config)

        assert provider_config.api_key == "test-key"

    def test_for_model_anthropic(self) -> None:
        """Test for_model with Anthropic model."""
        config: AiConfig = {"anthropic": {"api_key": "test-anthropic-key"}}

        provider_config = AnyProviderConfig.for_model("claude-3-opus", config)

        assert provider_config.api_key == "test-anthropic-key"

    def test_for_model_unknown_defaults_to_ollama(self) -> None:
        """Test for_model with unknown provider defaults to Ollama."""
        config: AiConfig = {"ollama": {"api_key": "test-key"}}

        provider_config = AnyProviderConfig.for_model("unknown-model", config)

        assert provider_config.api_key == "test-key"

    def test_for_model_unknown_provider_defaults_to_openai_compatible(
        self,
    ) -> None:
        """Test for_model with unknown provider defaults to OpenAI compatible."""
        config: AiConfig = {
            "open_ai_compatible": {"api_key": "test-key"},
            "open_ai": {"api_key": "other-key"},
        }

        provider_config = AnyProviderConfig.for_model(
            "provider/unknown-model", config
        )

        assert provider_config.api_key == "test-key"

        # Fallback to OpenAI if OpenAI compatible is not configured
        config: AiConfig = {
            "open_ai": {"api_key": "other-key"},
        }

        provider_config = AnyProviderConfig.for_model(
            "provider/unknown-model", config
        )

        assert provider_config.api_key == "other-key"

    @patch("marimo._server.ai.config._get_tools")
    def test_tools_included_when_available(self, mock_get_tools: Any) -> None:
        """Test that tools are included when available."""
        mock_tool = Tool(
            name="test_tool",
            description="Test tool",
            parameters={},
            source="backend",
            mode=["manual"],
        )
        mock_get_tools.return_value = [mock_tool]

        config: AiConfig = {
            "open_ai": {"api_key": "test-key"},
            "mode": "manual",
        }

        provider_config = AnyProviderConfig.for_openai(config)

        assert len(provider_config.tools) == 1
        assert provider_config.tools[0] == mock_tool

    @patch("marimo._server.ai.config._get_tools")
    def test_tools_excluded_when_empty(self, mock_get_tools: Any) -> None:
        """Test that tools are excluded when empty to prevent errors with deepseek."""
        mock_get_tools.return_value = []

        config: AiConfig = {
            "open_ai": {"api_key": "test-key"},
            "mode": "manual",
        }

        provider_config = AnyProviderConfig.for_openai(config)

        assert provider_config.tools == []


class TestOsKey:
    """Tests for os_key method."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"})
    def test_os_key_exists(self) -> None:
        """Test os_key returns value when environment variable exists."""
        result = AnyProviderConfig.os_key("OPENAI_API_KEY")
        assert result == "test-api-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_os_key_not_exists(self) -> None:
        """Test os_key returns None when environment variable doesn't exist."""
        result = AnyProviderConfig.os_key("NONEXISTENT_KEY")
        assert result is None

    @patch.dict(os.environ, {"EMPTY_KEY": ""})
    def test_os_key_empty_string(self) -> None:
        """Test os_key returns empty string when environment variable is empty."""
        result = AnyProviderConfig.os_key("EMPTY_KEY")
        assert result == ""


class TestProviderConfigWithFallback:
    """Tests for provider config methods with OS environment fallback."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-openai-key"})
    def test_for_openai_with_fallback_key(self) -> None:
        """Test OpenAI config uses fallback key when config is missing api_key."""
        config: AiConfig = {"open_ai": {}}

        provider_config = AnyProviderConfig.for_openai(config)

        assert provider_config.api_key == "env-openai-key"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-openai-key"})
    def test_for_openai_config_key_takes_precedence(self) -> None:
        """Test OpenAI config key takes precedence over environment variable."""
        config: AiConfig = {"open_ai": {"api_key": "config-openai-key"}}

        provider_config = AnyProviderConfig.for_openai(config)

        assert provider_config.api_key == "config-openai-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_for_openai_no_fallback_available(self) -> None:
        """Test OpenAI config fails when no config key and no env var."""
        config: AiConfig = {"open_ai": {}}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_openai(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "OpenAI API key not configured" in str(exc_info.value.detail)

    @patch.dict(os.environ, {"AZURE_API_KEY": "env-azure-key"})
    def test_for_azure_with_fallback_key(self) -> None:
        """Test Azure config uses fallback key when config is missing api_key."""
        config: AiConfig = {
            "azure": {"base_url": "https://test.openai.azure.com"}
        }

        provider_config = AnyProviderConfig.for_azure(config)

        assert provider_config.api_key == "env-azure-key"

    @patch.dict(os.environ, {"AZURE_API_KEY": "env-azure-key"})
    def test_for_azure_config_key_takes_precedence(self) -> None:
        """Test Azure config key takes precedence over environment variable."""
        config: AiConfig = {
            "azure": {
                "api_key": "config-azure-key",
                "base_url": "https://test.openai.azure.com",
            }
        }

        provider_config = AnyProviderConfig.for_azure(config)

        assert provider_config.api_key == "config-azure-key"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-anthropic-key"})
    def test_for_anthropic_with_fallback_key(self) -> None:
        """Test Anthropic config uses fallback key when config is missing api_key."""
        config: AiConfig = {"anthropic": {}}

        provider_config = AnyProviderConfig.for_anthropic(config)

        assert provider_config.api_key == "env-anthropic-key"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-anthropic-key"})
    def test_for_anthropic_config_key_takes_precedence(self) -> None:
        """Test Anthropic config key takes precedence over environment variable."""
        config: AiConfig = {"anthropic": {"api_key": "config-anthropic-key"}}

        provider_config = AnyProviderConfig.for_anthropic(config)

        assert provider_config.api_key == "config-anthropic-key"

    @patch.dict(os.environ, {"GEMINI_API_KEY": "env-gemini-key"})
    def test_for_google_with_gemini_fallback_key(self) -> None:
        """Test Google config uses GEMINI_API_KEY fallback when config is missing api_key."""
        config: AiConfig = {"google": {}}

        provider_config = AnyProviderConfig.for_google(config)

        assert provider_config.api_key == "env-gemini-key"

    @patch.dict(os.environ, {"GOOGLE_API_KEY": "env-google-key"}, clear=True)
    def test_for_google_with_google_fallback_key(self) -> None:
        """Test Google config uses GOOGLE_API_KEY fallback when GEMINI_API_KEY is not available."""
        config: AiConfig = {"google": {}}

        provider_config = AnyProviderConfig.for_google(config)

        assert provider_config.api_key == "env-google-key"

    @patch.dict(
        os.environ,
        {
            "GEMINI_API_KEY": "env-gemini-key",
            "GOOGLE_API_KEY": "env-google-key",
        },
    )
    def test_for_google_gemini_takes_precedence_over_google(self) -> None:
        """Test Google config prefers GEMINI_API_KEY over GOOGLE_API_KEY."""
        config: AiConfig = {"google": {}}

        provider_config = AnyProviderConfig.for_google(config)

        assert provider_config.api_key == "env-gemini-key"

    @patch.dict(os.environ, {"GEMINI_API_KEY": "env-gemini-key"})
    def test_for_google_config_key_takes_precedence(self) -> None:
        """Test Google config key takes precedence over environment variables."""
        config: AiConfig = {"google": {"api_key": "config-google-key"}}

        provider_config = AnyProviderConfig.for_google(config)

        assert provider_config.api_key == "config-google-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_for_google_no_fallback_available(self) -> None:
        """Test Google config fails when no config key and no env vars."""
        config: AiConfig = {"google": {}}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_google(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Google AI API key not configured" in str(exc_info.value.detail)


class TestGetKey:
    """Tests for _get_key function."""

    def test_get_key_with_api_key(self):
        """Test getting API key from config."""
        config = {"api_key": "test-key"}

        result = _get_key(config, "Test Service")

        assert result == "test-key"

    def test_get_key_bedrock_profile(self):
        """Test getting Bedrock key with profile name."""
        config = {"profile_name": "aws-profile"}

        result = _get_key(config, "Bedrock")

        assert result == "profile:aws-profile"

    def test_get_key_bedrock_credentials(self):
        """Test getting Bedrock key with AWS credentials."""
        config = {
            "aws_access_key_id": "access-key",
            "aws_secret_access_key": "secret-key",
        }

        result = _get_key(config, "Bedrock")

        assert result == "access-key:secret-key"

    def test_get_key_bedrock_fallback(self):
        """Test Bedrock key fallback when no credentials."""
        config = {}

        result = _get_key(config, "Bedrock")

        assert result == ""

    def test_get_key_ollama_placeholder(self):
        """Test Ollama gets placeholder key for local URL."""
        config = {"base_url": "http://127.0.0.1:11434/"}

        result = _get_key(config, "Ollama")

        assert result == "ollama-placeholder"

    def test_get_key_invalid_config(self):
        """Test error when config is not a dict."""
        with pytest.raises(HTTPException) as exc_info:
            _get_key("invalid", "Test Service")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Invalid config" in str(exc_info.value.detail)

    def test_get_key_missing_api_key(self):
        """Test error when API key is missing."""
        config = {}

        with pytest.raises(HTTPException) as exc_info:
            _get_key(config, "Test Service")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Test Service API key not configured" in str(
            exc_info.value.detail
        )

    def test_get_key_empty_api_key(self):
        """Test error when API key is empty."""
        config = {"api_key": ""}

        with pytest.raises(HTTPException) as exc_info:
            _get_key(config, "Test Service")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Test Service API key not configured" in str(
            exc_info.value.detail
        )

    def test_get_key_none_api_key(self):
        """Test error when API key is None."""
        config = {"api_key": None}

        with pytest.raises(HTTPException) as exc_info:
            _get_key(config, "Test Service")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Test Service API key not configured" in str(
            exc_info.value.detail
        )

    def test_get_key_with_fallback_key(self):
        """Test using fallback key when api_key is missing."""
        config = {}

        result = _get_key(config, "Test Service", fallback_key="fallback-key")

        assert result == "fallback-key"

    def test_get_key_with_fallback_key_empty_api_key(self):
        """Test using fallback key when api_key is empty."""
        config = {"api_key": ""}

        result = _get_key(config, "Test Service", fallback_key="fallback-key")

        assert result == "fallback-key"

    def test_get_key_with_fallback_key_none_api_key(self):
        """Test using fallback key when api_key is None."""
        config = {"api_key": None}

        result = _get_key(config, "Test Service", fallback_key="fallback-key")

        assert result == "fallback-key"

    def test_get_key_config_takes_precedence_over_fallback(self):
        """Test that config api_key takes precedence over fallback_key."""
        config = {"api_key": "config-key"}

        result = _get_key(config, "Test Service", fallback_key="fallback-key")

        assert result == "config-key"

    def test_get_key_no_fallback_key_provided(self):
        """Test error when no fallback key provided and api_key missing."""
        config = {}

        with pytest.raises(HTTPException) as exc_info:
            _get_key(config, "Test Service", fallback_key=None)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Test Service API key not configured" in str(
            exc_info.value.detail
        )

    def test_get_key_empty_fallback_key(self):
        """Test error when fallback key is empty string."""
        config = {}

        with pytest.raises(HTTPException) as exc_info:
            _get_key(config, "Test Service", fallback_key="")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Test Service API key not configured" in str(
            exc_info.value.detail
        )

    def test_get_key_bedrock_profile_ignores_fallback(self):
        """Test that Bedrock profile handling ignores fallback key."""
        config = {"profile_name": "aws-profile"}

        result = _get_key(config, "Bedrock", fallback_key="fallback-key")

        assert result == "profile:aws-profile"

    def test_get_key_bedrock_credentials_ignores_fallback(self):
        """Test that Bedrock credentials handling ignores fallback key."""
        config = {
            "aws_access_key_id": "access-key",
            "aws_secret_access_key": "secret-key",
        }

        result = _get_key(config, "Bedrock", fallback_key="fallback-key")

        assert result == "access-key:secret-key"

    def test_get_key_ollama_placeholder_ignores_fallback(self):
        """Test that Ollama placeholder handling ignores fallback key."""
        config = {"base_url": "http://127.0.0.1:11434/"}

        result = _get_key(config, "Ollama", fallback_key="fallback-key")

        assert result == "ollama-placeholder"


class TestGetBaseUrl:
    """Tests for _get_base_url function."""

    def test_get_base_url_with_url(self):
        """Test getting base URL from config."""
        config = {"base_url": "https://api.example.com"}

        result = _get_base_url(config)

        assert result == "https://api.example.com"

    def test_get_base_url_bedrock_region(self):
        """Test getting Bedrock base URL from region."""
        config = {"region_name": "us-east-1"}

        result = _get_base_url(config, "Bedrock")

        assert result == "us-east-1"

    def test_get_base_url_bedrock_without_name_param(self):
        """Test that Bedrock base URL is None when name param is not passed."""
        config = {"region_name": "us-east-1"}

        result = _get_base_url(config)  # No name parameter

        assert result is None

    def test_get_base_url_bedrock_no_region(self):
        """Test Bedrock base URL when no region specified."""
        config = {}

        result = _get_base_url(config, "Bedrock")

        assert result is None

    def test_get_base_url_missing(self):
        """Test when base URL is not in config."""
        config = {}

        result = _get_base_url(config)

        assert result is None

    def test_get_base_url_invalid_config(self):
        """Test error when config is not a dict."""
        with pytest.raises(HTTPException) as exc_info:
            _get_base_url("invalid")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Invalid config" in str(exc_info.value.detail)


class TestGetAiConfig:
    """Tests for _get_ai_config function."""

    def test_get_ai_config_success(self):
        """Test successful retrieval of AI config."""
        config: AiConfig = {"open_ai": {"api_key": "test-key"}}

        result = _get_ai_config(config, "open_ai", "OpenAI")

        assert result == {"api_key": "test-key"}

    def test_get_ai_config_missing_key(self):
        """Test error when AI config key is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            _get_ai_config(config, "open_ai", "OpenAI")

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "OpenAI config not found" in str(exc_info.value.detail)


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_get_model_with_openai_config(self):
        """Test getting model from OpenAI config."""
        config: AiConfig = {
            "models": {
                "chat_model": "gpt-4",
                "edit_model": "gpt-5",
                "displayed_models": [],
                "custom_models": [],
            },
            "open_ai": {"api_key": "test-key"},
        }

        result = get_chat_model(config)
        assert result == "gpt-4"

        result = get_edit_model(config)
        assert result == "gpt-5"

    def test_get_model_default(self):
        """Test getting default model when not specified."""
        config: AiConfig = {
            "models": {
                "displayed_models": [],
                "custom_models": [],
            },
            "open_ai": {"api_key": "test-key"},
        }

        result = get_chat_model(config)
        assert result == DEFAULT_MODEL

        result = get_edit_model(config)
        assert result == DEFAULT_MODEL

        result = get_autocomplete_model({"ai": config})
        assert result == DEFAULT_MODEL

    def test_get_max_tokens_from_config(self):
        """Test getting max tokens from config."""
        config = cast(
            MarimoConfig,
            {
                "ai": {"max_tokens": 2048},
            },
        )

        result = get_max_tokens(config)

        assert result == 2048

    def test_get_max_tokens_default_no_ai_config(self):
        """Test getting default max tokens when no AI config."""
        config = cast(
            MarimoConfig,
            {
                "completion": {"activate_on_typing": True, "copilot": False},
            },
        )

        result = get_max_tokens(config)

        assert result == DEFAULT_MAX_TOKENS

    def test_get_max_tokens_default_no_max_tokens(self):
        """Test getting default max tokens when max_tokens not specified."""
        config = cast(
            MarimoConfig,
            {
                "ai": {},
            },
        )

        result = get_max_tokens(config)

        assert result == DEFAULT_MAX_TOKENS

    def test_get_autocomplete_model(self) -> None:
        """Test get_autocomplete_model with new ai.models.autocomplete_model config."""

        config: AiConfig = {
            "models": {
                "chat_model": "openai/gpt-4o",
                "edit_model": "openai/gpt-4o-mini",
                "autocomplete_model": "openai/gpt-3.5-turbo-instruct",
                "displayed_models": [],
                "custom_models": [],
            }
        }

        assert (
            get_autocomplete_model({"ai": config})
            == "openai/gpt-3.5-turbo-instruct"
        )

    def test_get_chat_model(self) -> None:
        """Test get_chat_model with new ai.models.chat_model config."""

        config: AiConfig = {
            "models": {
                "chat_model": "anthropic/claude-3-5-sonnet-20241022",
                "edit_model": "openai/gpt-4o-mini",
                "displayed_models": [],
                "custom_models": [],
            }
        }

        assert get_chat_model(config) == "anthropic/claude-3-5-sonnet-20241022"

    def test_get_edit_model(self) -> None:
        """Test get_edit_model with new ai.models.edit_model config."""

        config: AiConfig = {
            "models": {
                "chat_model": "openai/gpt-4o",
                "edit_model": "anthropic/claude-3-5-haiku-20241022",
                "displayed_models": [],
                "custom_models": [],
            }
        }

        assert get_edit_model(config) == "anthropic/claude-3-5-haiku-20241022"

    def test_get_edit_model_fallback_to_chat_model(self) -> None:
        """Test get_edit_model falls back to chat_model when edit_model is not set."""

        config: AiConfig = {
            "models": {
                "chat_model": "openai/gpt-4o",
                "displayed_models": [],
                "custom_models": [],
                # Note: no edit_model
            }
        }

        assert get_edit_model(config) == "openai/gpt-4o"

    def test_get_models_with_legacy_openai_config(self) -> None:
        """Test that the new get_*_model functions work with legacy open_ai.model config."""
        config: AiConfig = {
            "open_ai": {
                "api_key": "test-key",
                "model": "gpt-4-legacy",
            }
        }

        # Should fall back to open_ai.model for both chat and edit
        assert get_chat_model(config) == "gpt-4-legacy"
        assert get_edit_model(config) == "gpt-4-legacy"
        assert get_autocomplete_model({"ai": config}) == DEFAULT_MODEL

    def test_for_model_with_autocomplete_model(self) -> None:
        """Test AnyProviderConfig.for_model works with autocomplete models from new config."""
        config: AiConfig = {
            "open_ai": {"api_key": "test-key"},
            "models": {
                "autocomplete_model": "openai/gpt-3.5-turbo-instruct",
                "displayed_models": [],
                "custom_models": [],
            },
        }

        provider_config = AnyProviderConfig.for_model(
            "openai/gpt-3.5-turbo-instruct", config
        )

        assert provider_config.api_key == "test-key"
        assert provider_config.tools == []  # Autocomplete should have no tools


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_openai_config_missing(self):
        """Test error when OpenAI config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_openai(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "OpenAI config not found" in str(exc_info.value.detail)

    def test_anthropic_config_missing(self):
        """Test error when Anthropic config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_anthropic(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Anthropic config not found" in str(exc_info.value.detail)

    def test_google_config_missing(self):
        """Test error when Google config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_google(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Google AI config not found" in str(exc_info.value.detail)

    def test_bedrock_config_missing(self):
        """Test error when Bedrock config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_bedrock(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Bedrock config not found" in str(exc_info.value.detail)

    def test_azure_config_missing(self):
        """Test error when Azure config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_azure(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Azure OpenAI config not found" in str(exc_info.value.detail)

    def test_ollama_config_missing(self):
        """Test error when Ollama config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_ollama(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "Ollama config not found" in str(exc_info.value.detail)

    def test_openai_compatible_config_missing(self):
        """Test error when OpenAI Compatible config is missing."""
        config: AiConfig = {}

        with pytest.raises(HTTPException) as exc_info:
            AnyProviderConfig.for_openai_compatible(config)

        assert exc_info.value.status_code == HTTPStatus.BAD_REQUEST
        assert "OpenAI Compatible config not found" in str(
            exc_info.value.detail
        )
