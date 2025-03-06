from __future__ import annotations

import os
from typing import Any, Optional, cast
from unittest.mock import MagicMock, patch

import pytest

from marimo._ai._types import ChatMessage, ChatModelConfig
from marimo._ai.llm._impl import (
    DEFAULT_SYSTEM_MESSAGE,
    anthropic,
    google,
    groq,
    openai,
    simple,
)
from marimo._dependencies.dependencies import DependencyManager


def test_simple_model() -> None:
    """Test the simple model wrapper."""
    model = simple(lambda x: x * 2)
    assert (
        model([ChatMessage(role="user", content="hey")], ChatModelConfig())
        == "heyhey"
    )

    assert (
        model(
            [
                ChatMessage(role="user", content="hey", attachments=[]),
                ChatMessage(role="user", content="goodbye", attachments=[]),
            ],
            ChatModelConfig(),
        )
        == "goodbyegoodbye"
    )


@pytest.mark.skipif(
    not DependencyManager.google_ai.has(), reason="Google AI is not installed"
)
class TestGoogle:
    def test_init(self) -> None:
        """Test initialization of the google class."""
        model = google("gemini-pro")
        assert model.model == "gemini-pro"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None

        model = google(
            "gemini-pro",
            system_message="Custom system message",
            api_key="test-key",
        )
        assert model.model == "gemini-pro"
        assert model.system_message == "Custom system message"
        assert model.api_key == "test-key"

    @patch.object(google, "_require_api_key")
    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_call(
        self,
        mock_generative_model: MagicMock,
        mock_configure: MagicMock,
        mock_require_api_key: MagicMock,
    ) -> None:
        """Test calling the google class."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_generative_model.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_client.generate_content.return_value = mock_response

        model = google("gemini-pro")
        # Patch the _require_api_key property to return the test key directly
        with patch.object(model, "_require_api_key", "test-key"):
            messages = [ChatMessage(role="user", content="Test prompt")]
            config = ChatModelConfig(
                max_tokens=100,
                temperature=0.7,
                top_p=0.9,
                top_k=10,
                frequency_penalty=0.5,
                presence_penalty=0.5,
            )

            result = model(messages, config)
            assert result == "Test response"

            mock_configure.assert_called_once_with(api_key="test-key")
        mock_generative_model.assert_called_once()
        call_args = mock_generative_model.call_args[1]
        assert call_args["model_name"] == "gemini-pro"
        generation_config = call_args["generation_config"]
        assert generation_config.max_output_tokens == 100
        assert generation_config.temperature == 0.7
        assert generation_config.top_p == 0.9
        assert generation_config.top_k == 10
        assert generation_config.frequency_penalty == 0.5
        assert generation_config.presence_penalty == 0.5

        mock_client.generate_content.assert_called_once()

    @patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "env-key"})
    def test_require_api_key_env(self) -> None:
        """Test _require_api_key with environment variable."""
        model = google("gemini-pro")
        assert model._require_api_key == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_config(self, mock_get_context: MagicMock) -> None:
        """Test _require_api_key with config."""
        mock_context = MagicMock()
        mock_context.marimo_config = {
            "ai": {"google": {"api_key": "config-key"}}
        }
        mock_get_context.return_value = mock_context

        model = google("gemini-pro")
        assert model._require_api_key == "config-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_missing(
        self, mock_get_context: MagicMock
    ) -> None:
        """Test _require_api_key with missing key."""
        mock_context = MagicMock()
        mock_context.marimo_config = {"ai": {"google": {"api_key": ""}}}
        mock_get_context.return_value = mock_context

        model = google("gemini-pro")
        with pytest.raises(ValueError):
            _ = model._require_api_key


@pytest.mark.skipif(
    not DependencyManager.groq.has(), reason="Groq is not installed"
)
class TestGroq:
    def test_init(self) -> None:
        """Test initialization of the groq class."""
        model = groq("llama3-70b-8192")
        assert model.model == "llama3-70b-8192"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None
        assert model.base_url is None

        model = groq(
            "llama3-70b-8192",
            system_message="Custom system message",
            api_key="test-key",
            base_url="https://example.com",
        )
        assert model.model == "llama3-70b-8192"
        assert model.system_message == "Custom system message"
        assert model.api_key == "test-key"
        assert model.base_url == "https://example.com"

    @patch.object(groq, "_require_api_key")
    @patch("groq.Groq")
    def test_call(
        self, mock_groq_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the groq class."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        model = groq("llama3-70b-8192")
        # Patch the _require_api_key property to return the test key directly
        with patch.object(model, "_require_api_key", "test-key"):
            messages = [ChatMessage(role="user", content="Test prompt")]
            config = ChatModelConfig(
                max_tokens=100,
                temperature=0.7,
                top_p=0.9,
            )

            result = model(messages, config)
            assert result == "Test response"

            mock_groq_class.assert_called_once_with(
                api_key="test-key", base_url=None
            )
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "llama3-70b-8192"
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == "Test prompt"
        assert call_args["max_tokens"] == 100
        assert call_args["temperature"] == 0.7
        assert call_args["top_p"] == 0.9
        assert call_args["stop"] is None
        assert call_args["stream"] is False

    @patch.dict(os.environ, {"GROQ_API_KEY": "env-key"})
    def test_require_api_key_env(self) -> None:
        """Test _require_api_key with environment variable."""
        model = groq("llama3-70b-8192")
        assert model._require_api_key == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    def test_require_api_key_missing(self) -> None:
        """Test _require_api_key with missing key."""
        model = groq("llama3-70b-8192")
        with pytest.raises(ValueError):
            _ = model._require_api_key


@pytest.mark.skipif(
    DependencyManager.openai.has(), reason="OpenAI is installed"
)
def test_openai_require() -> None:
    """Test that openai.require raises ModuleNotFoundError."""
    model = openai("gpt-4")
    messages = [ChatMessage(role="user", content="Test prompt")]
    config = ChatModelConfig()
    with pytest.raises(ModuleNotFoundError):
        model(messages, config)


@pytest.mark.skipif(
    DependencyManager.anthropic.has(), reason="Anthropic is installed"
)
def test_anthropic_require() -> None:
    """Test that anthropic.require raises ModuleNotFoundError."""
    model = anthropic("claude-3-opus-20240229")
    messages = [ChatMessage(role="user", content="Test prompt")]
    config = ChatModelConfig()
    with pytest.raises(ModuleNotFoundError):
        model(messages, config)


@pytest.mark.skipif(
    DependencyManager.google_ai.has(), reason="Google AI is installed"
)
def test_google_require() -> None:
    """Test that google.require raises ModuleNotFoundError."""
    model = google("gemini-pro")
    messages = [ChatMessage(role="user", content="Test prompt")]
    config = ChatModelConfig()
    with pytest.raises(ModuleNotFoundError):
        model(messages, config)


@pytest.mark.skipif(DependencyManager.groq.has(), reason="Groq is installed")
def test_groq_require() -> None:
    """Test that groq.require raises ModuleNotFoundError."""
    model = groq("llama3-70b-8192")
    messages = [ChatMessage(role="user", content="Test prompt")]
    config = ChatModelConfig()
    with pytest.raises(ModuleNotFoundError):
        model(messages, config)


@pytest.mark.skipif(
    not DependencyManager.openai.has(), reason="OpenAI is not installed"
)
class TestOpenAI:
    def test_init(self) -> None:
        """Test initialization of the openai class."""
        model = openai("gpt-4")
        assert model.model == "gpt-4"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None
        assert model.base_url is None

        model = openai(
            "gpt-4",
            system_message="Custom system message",
            api_key="test-key",
            base_url="https://example.com",
        )
        assert model.model == "gpt-4"
        assert model.system_message == "Custom system message"
        assert model.api_key == "test-key"
        assert model.base_url == "https://example.com"

    @patch.object(openai, "_require_api_key")
    @patch("openai.OpenAI")
    def test_call(
        self, mock_openai_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the openai class."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        model = openai("gpt-4")
        # Patch the _require_api_key property to return the test key directly
        with patch.object(model, "_require_api_key", "test-key"):
            messages = [ChatMessage(role="user", content="Test prompt")]
            config = ChatModelConfig(
                max_tokens=100,
                temperature=0.7,
                top_p=0.9,
                frequency_penalty=0.5,
                presence_penalty=0.5,
            )

            result = model(messages, config)
            assert result == "Test response"

            mock_openai_class.assert_called_once_with(
                api_key="test-key", base_url=None
            )
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4"
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == "Test prompt"
        assert call_args["max_tokens"] == 100
        assert call_args["temperature"] == 0.7
        assert call_args["top_p"] == 0.9
        assert call_args["frequency_penalty"] == 0.5
        assert call_args["presence_penalty"] == 0.5
        assert call_args["stream"] is False

    @patch.object(openai, "_require_api_key")
    @patch("openai.AzureOpenAI")
    def test_call_azure(
        self,
        mock_azure_openai_class: MagicMock,
        mock_require_api_key: MagicMock,
    ) -> None:
        """Test calling the openai class with Azure OpenAI."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_azure_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        model = openai(
            "gpt-4",
            base_url="https://example.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-05-15",
        )
        # Patch the _require_api_key property to return the test key directly
        with patch.object(model, "_require_api_key", "test-key"):
            messages = [ChatMessage(role="user", content="Test prompt")]
            config = ChatModelConfig()

            result = model(messages, config)
            assert result == "Test response"

            mock_azure_openai_class.assert_called_once_with(
                api_key="test-key",
                api_version="2023-05-15",
                azure_endpoint="https://example.openai.azure.com",
            )
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4"

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"})
    def test_require_api_key_env(self) -> None:
        """Test _require_api_key with environment variable."""
        model = openai("gpt-4")
        assert model._require_api_key == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_config(self, mock_get_context: MagicMock) -> None:
        """Test _require_api_key with config."""
        mock_context = MagicMock()
        mock_context.marimo_config = {
            "ai": {"open_ai": {"api_key": "config-key"}}
        }
        mock_get_context.return_value = mock_context

        model = openai("gpt-4")
        assert model._require_api_key == "config-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_missing(
        self, mock_get_context: MagicMock
    ) -> None:
        """Test _require_api_key with missing key."""
        mock_context = MagicMock()
        mock_context.marimo_config = {"ai": {"open_ai": {"api_key": ""}}}
        mock_get_context.return_value = mock_context

        model = openai("gpt-4")
        with pytest.raises(ValueError):
            _ = model._require_api_key


@pytest.mark.skipif(
    not DependencyManager.anthropic.has(), reason="Anthropic is not installed"
)
class TestAnthropic:
    def test_init(self) -> None:
        """Test initialization of the anthropic class."""
        model = anthropic("claude-3-opus-20240229")
        assert model.model == "claude-3-opus-20240229"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None
        assert model.base_url is None

        model = anthropic(
            "claude-3-opus-20240229",
            system_message="Custom system message",
            api_key="test-key",
            base_url="https://example.com",
        )
        assert model.model == "claude-3-opus-20240229"
        assert model.system_message == "Custom system message"
        assert model.api_key == "test-key"
        assert model.base_url == "https://example.com"

    @patch.object(anthropic, "_require_api_key")
    @patch("anthropic.Anthropic")
    def test_call(
        self, mock_anthropic_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the anthropic class."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = "Test response"
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response

        model = anthropic("claude-3-opus-20240229")
        # Patch the _require_api_key property to return the test key directly
        with patch.object(model, "_require_api_key", "test-key"):
            messages = [ChatMessage(role="user", content="Test prompt")]
            config = ChatModelConfig(
                max_tokens=100,
                temperature=0.7,
                top_p=0.9,
                top_k=10,
            )

            result = model(messages, config)
            assert result == "Test response"

            mock_anthropic_class.assert_called_once_with(
                api_key="test-key", base_url=None
            )
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args[1]
        assert call_args["model"] == "claude-3-opus-20240229"
        assert call_args["system"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["max_tokens"] == 100
        assert call_args["temperature"] == 0.7
        assert call_args["top_p"] == 0.9
        assert call_args["top_k"] == 10
        assert call_args["stream"] is False

    @patch.object(anthropic, "_require_api_key")
    @patch("anthropic.Anthropic")
    def test_call_tool_use(
        self, mock_anthropic_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the anthropic class with tool use response."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "tool_use"
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response

        model = anthropic("claude-3-opus-20240229")
        messages = [ChatMessage(role="user", content="Test prompt")]
        config = ChatModelConfig()

        result = model(messages, config)
        assert result == [mock_content]

    @patch.object(anthropic, "_require_api_key")
    @patch("anthropic.Anthropic")
    def test_call_empty_content(
        self, mock_anthropic_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the anthropic class with empty content."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response

        model = anthropic("claude-3-opus-20240229")
        messages = [ChatMessage(role="user", content="Test prompt")]
        config = ChatModelConfig()

        result = model(messages, config)
        assert result == ""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"})
    def test_require_api_key_env(self) -> None:
        """Test _require_api_key with environment variable."""
        model = anthropic("claude-3-opus-20240229")
        assert model._require_api_key == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_config(self, mock_get_context: MagicMock) -> None:
        """Test _require_api_key with config."""
        mock_context = MagicMock()
        mock_context.marimo_config = {
            "ai": {"anthropic": {"api_key": "config-key"}}
        }
        mock_get_context.return_value = mock_context

        model = anthropic("claude-3-opus-20240229")
        assert model._require_api_key == "config-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_missing(
        self, mock_get_context: MagicMock
    ) -> None:
        """Test _require_api_key with missing key."""
        mock_context = MagicMock()
        mock_context.marimo_config = {"ai": {"anthropic": {"api_key": ""}}}
        mock_get_context.return_value = mock_context

        model = anthropic("claude-3-opus-20240229")
        with pytest.raises(ValueError):
            _ = model._require_api_key
