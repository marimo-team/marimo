# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

import pytest
from starlette.exceptions import HTTPException

from marimo._config.config import (
    AiConfig,
    CompletionConfig,
    MarimoConfig,
)
from marimo._server.ai.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    AnyProviderConfig,
    _get_ai_config,
    _get_base_url,
    _get_key,
    get_max_tokens,
    get_model,
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

    def test_for_completion(self):
        """Test completion configuration."""
        config: CompletionConfig = {
            "activate_on_typing": True,
            "copilot": "custom",
            "api_key": "test-completion-key",
            "base_url": "https://completion.service.com",
        }

        provider_config = AnyProviderConfig.for_completion(config)

        assert provider_config.api_key == "test-completion-key"
        assert provider_config.base_url == "https://completion.service.com"
        assert provider_config.tools == []  # Completion never uses tools

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
            "open_ai": {"model": "gpt-4", "api_key": "test-key"}
        }

        result = get_model(config)

        assert result == "gpt-4"

    def test_get_model_default(self):
        """Test getting default model when not specified."""
        config: AiConfig = {"open_ai": {"api_key": "test-key"}}

        result = get_model(config)

        assert result == DEFAULT_MODEL

    def test_get_model_no_openai_config(self):
        """Test getting default model when no OpenAI config."""
        config: AiConfig = {}

        result = get_model(config)

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
