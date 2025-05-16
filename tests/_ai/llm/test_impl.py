"""Tests for the LLM implementations in marimo._ai.llm._impl."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from marimo._ai._types import ChatMessage, ChatModelConfig
from marimo._ai.llm._impl import (
    DEFAULT_SYSTEM_MESSAGE,
    anthropic,
    bedrock,
    google,
    groq,
    openai,
    simple,
)
from marimo._dependencies.dependencies import DependencyManager


@pytest.fixture
def mock_openai_client():
    """Fixture for mocking the OpenAI client."""
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Setup the response structure
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        yield mock_client, mock_openai_class


@pytest.fixture
def mock_groq_client():
    """Fixture for mocking the Groq client."""
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client

        # Setup the response structure
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        yield mock_client, mock_groq_class


@pytest.fixture
def mock_anthropic_client():
    """Fixture for mocking the Anthropic client."""
    with patch("anthropic.Anthropic") as mock_anthropic_class:
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Setup the response structure
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Test response")]
        mock_response.content = mock_message.content
        mock_client.messages.create.return_value = mock_response

        yield mock_client, mock_anthropic_class


@pytest.fixture
def mock_google_client():
    """Fixture for mocking the Google client."""
    with patch("google.generativeai.GenerativeModel") as mock_google_class:
        mock_client = MagicMock()
        mock_google_class.return_value = mock_client

        # Setup the response structure
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_client.generate_content.return_value = mock_response

        yield mock_client, mock_google_class


@pytest.fixture
def mock_azure_openai_client():
    """Fixture for mocking the Azure OpenAI client."""
    with patch("openai.AzureOpenAI") as mock_azure_openai_class:
        mock_client = MagicMock()
        mock_azure_openai_class.return_value = mock_client

        # Setup the response structure
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        yield mock_client, mock_azure_openai_class


@pytest.fixture
def mock_litellm_completion():
    """Fixture for mocking the OpenAI client."""
    with patch("litellm.completion") as mock_litellm_completion:
        # Setup the response structure
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Test response"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_litellm_completion.return_value = mock_response

        yield mock_litellm_completion


@pytest.fixture
def test_messages():
    """Fixture for test messages."""
    return [ChatMessage(role="user", content="Test prompt")]


@pytest.fixture
def test_config():
    """Fixture for test configuration."""
    return ChatModelConfig(
        max_tokens=100,
        temperature=0.7,
        top_p=0.9,
        frequency_penalty=0.5,
        presence_penalty=0.5,
    )


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


@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Mock environment variables."""
    with patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "test-key",
            "GOOGLE_AI_API_KEY": "test-key",
        },
        clear=True,
    ):
        yield


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
    """Tests for the OpenAI class."""

    def test_init(self):
        """Test initialization of the openai class."""
        # Test default initialization
        model = openai("gpt-4")
        assert model.model == "gpt-4"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None
        assert model.base_url is None

        # Test custom initialization
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

    def test_call(self, mock_openai_client, test_messages, test_config):
        """Test calling the openai class with standard OpenAI client."""
        mock_client, mock_openai_class = mock_openai_client

        # Create model with API key to avoid _require_api_key
        model = openai("gpt-4", api_key="test-key")

        result = model(test_messages, test_config)

        # Verify result
        assert result == "Test response"

        # Verify client initialization
        mock_openai_class.assert_called_once_with(
            api_key="test-key", base_url=None
        )

        # Verify API call
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4"
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == "Test prompt"
        assert call_args["max_completion_tokens"] == 100
        # Use pytest.approx for floating point comparisons
        assert call_args["temperature"] == pytest.approx(0.7)
        assert call_args["top_p"] == pytest.approx(0.9)
        assert call_args["frequency_penalty"] == pytest.approx(0.5)
        assert call_args["presence_penalty"] == pytest.approx(0.5)
        assert call_args["stream"] is False

    def test_call_with_base_url(
        self, mock_openai_client, test_messages, test_config
    ):
        """Test calling the openai class with a custom base URL."""
        mock_client, mock_openai_class = mock_openai_client

        # Create model with API key and base URL
        model = openai(
            "gpt-4", api_key="test-key", base_url="https://example.com"
        )

        result = model(test_messages, test_config)

        # Verify result
        assert result == "Test response"

        # Verify client initialization with base URL
        mock_openai_class.assert_called_once_with(
            api_key="test-key", base_url="https://example.com"
        )

    def test_call_azure(
        self, mock_azure_openai_client, test_messages, test_config
    ):
        """Test calling the openai class with Azure OpenAI."""
        mock_client, mock_azure_openai_class = mock_azure_openai_client

        # Create model with API key and Azure URL
        model = openai(
            "gpt-4",
            api_key="test-key",
            base_url="https://example.openai.azure.com/openai/deployments/gpt-4/chat/completions?api-version=2023-05-15",
        )

        result = model(test_messages, test_config)

        # Verify result
        assert result == "Test response"

        # Verify Azure client initialization
        mock_azure_openai_class.assert_called_once_with(
            api_key="test-key",
            api_version="2023-05-15",
            azure_endpoint="https://example.openai.azure.com",
        )

        # Verify API call
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "gpt-4"

    def test_call_with_empty_response(
        self, mock_openai_client, test_messages, test_config
    ):
        """Test calling the openai class with an empty response."""
        mock_client, _ = mock_openai_client

        # Modify the mock to return an empty content
        mock_client.chat.completions.create.return_value.choices[
            0
        ].message.content = None

        # Create model with API key
        model = openai("gpt-4", api_key="test-key")

        result = model(test_messages, test_config)

        # Verify empty string is returned when content is None
        assert result == ""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"})
    def test_require_api_key_env(self):
        """Test _require_api_key with environment variable."""
        model = openai("gpt-4")
        assert model._require_api_key == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_config(self, mock_get_context):
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
    def test_require_api_key_missing(self, mock_get_context):
        """Test _require_api_key with missing key."""
        mock_context = MagicMock()
        mock_context.marimo_config = {"ai": {"open_ai": {"api_key": ""}}}
        mock_get_context.return_value = mock_context

        model = openai("gpt-4")
        with pytest.raises(ValueError, match="openai api key not provided"):
            _ = model._require_api_key

    @patch(
        "marimo._dependencies.dependencies.DependencyManager.openai.require"
    )
    def test_dependency_check(self, mock_require):
        """Test that the dependency check is performed."""
        # Create model with API key to avoid _require_api_key issues
        model = openai("gpt-4", api_key="test-key")

        # Mock OpenAI and related imports
        with patch("openai.OpenAI") as mock_openai_class:
            # Setup mock client and response
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Test response"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response

            # Call the model
            model(
                [ChatMessage(role="user", content="Test")], ChatModelConfig()
            )

            # Verify dependency check was called
            mock_require.assert_called_once_with(
                "chat model requires openai. `pip install openai`"
            )

    def test_convert_to_openai_messages(self):
        """Test that messages are properly converted for OpenAI."""
        # Create model with API key to avoid _require_api_key issues
        model = openai("gpt-4", api_key="test-key")

        with patch("openai.OpenAI") as mock_openai_class:
            # Setup mock client and response
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Test response"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response

            # Test with multiple messages
            messages = [
                ChatMessage(role="system", content="Custom system"),
                ChatMessage(role="user", content="Hello"),
                ChatMessage(role="assistant", content="Hi there"),
                ChatMessage(role="user", content="How are you?"),
            ]

            model(messages, ChatModelConfig())

            # Verify the messages were properly converted
            call_args = mock_client.chat.completions.create.call_args[1]
            assert len(call_args["messages"]) == 5  # system + all messages
            assert call_args["messages"][0]["role"] == "system"
            assert (
                call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
            )
            assert call_args["messages"][1]["role"] == "system"
            assert call_args["messages"][1]["content"] == "Custom system"
            assert call_args["messages"][2]["role"] == "user"
            assert call_args["messages"][2]["content"] == "Hello"
            assert call_args["messages"][3]["role"] == "assistant"
            assert call_args["messages"][3]["content"] == "Hi there"
            assert call_args["messages"][4]["role"] == "user"
            assert call_args["messages"][4]["content"] == "How are you?"


@pytest.mark.skipif(
    not DependencyManager.groq.has(), reason="Groq is not installed"
)
class TestGroq:
    """Tests for the Groq class."""

    def test_init(self):
        """Test initialization of the groq class."""
        # Test default initialization
        model = groq("llama3-8b-8192")
        assert model.model == "llama3-8b-8192"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None
        assert model.base_url is None

        # Test custom initialization
        model = groq(
            "llama3-8b-8192",
            system_message="Custom system message",
            api_key="test-key",
            base_url="https://example.com",
        )
        assert model.model == "llama3-8b-8192"
        assert model.system_message == "Custom system message"
        assert model.api_key == "test-key"
        assert model.base_url == "https://example.com"

    def test_call(self, mock_groq_client, test_messages, test_config):
        """Test calling the groq class with standard Groq client."""
        mock_client, mock_groq_class = mock_groq_client

        # Create model with API key to avoid _require_api_key
        model = groq("llama3-8b-8192", api_key="test-key")

        result = model(test_messages, test_config)

        # Verify result
        assert result == "Test response"

        # Verify client initialization
        mock_groq_class.assert_called_once_with(
            api_key="test-key", base_url=None
        )

        # Verify API call
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args[1]
        assert call_args["model"] == "llama3-8b-8192"
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == "Test prompt"
        assert call_args["max_tokens"] == 100
        # Use pytest.approx for floating point comparisons
        assert call_args["temperature"] == pytest.approx(0.7)
        assert call_args["top_p"] == pytest.approx(0.9)
        assert call_args["frequency_penalty"] == pytest.approx(0.5)
        assert call_args["presence_penalty"] == pytest.approx(0.5)
        assert call_args["stream"] is False

    def test_call_with_base_url(
        self, mock_groq_client, test_messages, test_config
    ):
        """Test calling the groq class with a custom base URL."""
        mock_client, mock_groq_class = mock_groq_client

        # Create model with API key and base URL
        model = groq(
            "llama3-8b-8192",
            api_key="test-key",
            base_url="https://example.com",
        )

        result = model(test_messages, test_config)

        # Verify result
        assert result == "Test response"

        # Verify client initialization with base URL
        mock_groq_class.assert_called_once_with(
            api_key="test-key", base_url="https://example.com"
        )

    def test_call_with_empty_response(
        self, mock_groq_client, test_messages, test_config
    ):
        """Test calling the groq class with an empty response."""
        mock_client, _ = mock_groq_client

        # Modify the mock to return an empty content
        mock_client.chat.completions.create.return_value.choices[
            0
        ].message.content = None

        # Create model with API key
        model = groq("llama3-8b-8192", api_key="test-key")

        result = model(test_messages, test_config)

        # Verify empty string is returned when content is None
        assert result == ""

    @patch.dict(os.environ, {"GROQ_API_KEY": "env-key"})
    def test_require_api_key_env(self):
        """Test _require_api_key with environment variable."""
        model = groq("llama3-8b-8192")
        assert model._require_api_key == "env-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_config(self, mock_get_context):
        """Test _require_api_key with config."""
        mock_context = MagicMock()
        mock_context.marimo_config = {
            "ai": {"groq": {"api_key": "config-key"}}
        }
        mock_get_context.return_value = mock_context

        model = groq("llama3-8b-8192")
        assert model._require_api_key == "config-key"

    @patch.dict(os.environ, {}, clear=True)
    @patch("marimo._runtime.context.types.get_context")
    def test_require_api_key_missing(self, mock_get_context):
        """Test _require_api_key with missing key."""
        mock_context = MagicMock()
        mock_context.marimo_config = {"ai": {"groq": {"api_key": ""}}}
        mock_get_context.return_value = mock_context

        model = groq("llama3-8b-8192")
        with pytest.raises(ValueError, match="groq api key not provided"):
            _ = model._require_api_key

    @patch("marimo._dependencies.dependencies.DependencyManager.groq.require")
    def test_dependency_check(self, mock_require):
        """Test that the dependency check is performed."""
        # Create model with API key to avoid _require_api_key issues
        model = groq("llama3-8b-8192", api_key="test-key")

        # Mock Groq and related imports
        with patch("groq.Groq") as mock_groq_class:
            # Setup mock client and response
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Test response"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response

            # Call the model
            model(
                [ChatMessage(role="user", content="Test")], ChatModelConfig()
            )

            # Verify dependency check was called
            mock_require.assert_called_once_with(
                "chat model requires groq. `pip install groq`"
            )

    def test_convert_to_groq_messages(self):
        """Test that messages are properly converted for Groq."""
        # Create model with API key to avoid _require_api_key issues
        model = groq("llama3-8b-8192", api_key="test-key")

        with patch("groq.Groq") as mock_groq_class:
            # Setup mock client and response
            mock_client = MagicMock()
            mock_groq_class.return_value = mock_client
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_message = MagicMock()
            mock_message.content = "Test response"
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_client.chat.completions.create.return_value = mock_response

            # Test with multiple messages
            messages = [
                ChatMessage(role="system", content="Custom system"),
                ChatMessage(role="user", content="Hello"),
                ChatMessage(role="assistant", content="Hi there"),
                ChatMessage(role="user", content="How are you?"),
            ]

            model(messages, ChatModelConfig())

            # Verify the messages were properly converted
            call_args = mock_client.chat.completions.create.call_args[1]
            assert len(call_args["messages"]) == 5  # system + all messages
            assert call_args["messages"][0]["role"] == "system"
            assert (
                call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
            )
            assert call_args["messages"][1]["role"] == "system"
            assert call_args["messages"][1]["content"] == "Custom system"
            assert call_args["messages"][2]["role"] == "user"
            assert call_args["messages"][2]["content"] == "Hello"
            assert call_args["messages"][3]["role"] == "assistant"
            assert call_args["messages"][3]["content"] == "Hi there"
            assert call_args["messages"][4]["role"] == "user"
            assert call_args["messages"][4]["content"] == "How are you?"


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


@pytest.mark.skipif(
    not DependencyManager.boto3.has() or not DependencyManager.litellm.has(),
    reason="boto3 or litellm is not installed",
)
class TestBedrock:
    """Test the Bedrock model class"""

    def test_init(self):
        """Test initialization of the bedrock model class"""
        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            system_message="Test system message",
            region_name="us-east-1",
        )

        # bedrock automatically prefixes with bedrock/ for litellm usage
        assert model.model == "bedrock/anthropic.claude-3-sonnet-20240229"
        assert model.system_message == "Test system message"
        assert model.region_name == "us-east-1"
        assert model.profile_name is None
        assert model.aws_access_key_id is None
        assert model.aws_secret_access_key is None

    def test_init_with_credentials(self):
        """Test initialization with explicit credentials"""
        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        )

        assert model.aws_access_key_id == "test-key"
        assert model.aws_secret_access_key == "test-secret"

    def test_init_with_profile(self):
        """Test initialization with AWS profile"""
        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            profile_name="test-profile",
        )

        assert model.profile_name == "test-profile"

    def test_call(self, mock_litellm_completion, test_messages, test_config):
        """Test calling the bedrock class with LiteLLM client."""
        model_name = "anthropic.claude-3-sonnet-20240229"

        # Create model with API key to avoid _require_api_key
        model = bedrock(model_name)

        result = model(test_messages, test_config)

        # Verify result
        assert result == "Test response"

        # Verify API call
        mock_litellm_completion.assert_called_once()
        call_args = mock_litellm_completion.call_args[1]
        assert call_args["model"] == f"bedrock/{model_name}"
        assert len(call_args["messages"]) == 2
        assert call_args["messages"][0]["role"] == "system"
        assert call_args["messages"][0]["content"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == "Test prompt"
        assert call_args["max_tokens"] == 100
        # Use pytest.approx for floating point comparisons
        assert call_args["temperature"] == pytest.approx(0.7)
        assert call_args["top_p"] == pytest.approx(0.9)
        assert call_args["frequency_penalty"] == pytest.approx(0.5)
        assert call_args["presence_penalty"] == pytest.approx(0.5)
        assert call_args["stream"] is False
