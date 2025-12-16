"""Tests for the LLM implementations in marimo._ai.llm._impl."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from marimo._ai._types import ChatMessage, ChatModelConfig, TextPart
from marimo._ai.llm._impl import (
    DEFAULT_SYSTEM_MESSAGE,
    anthropic,
    bedrock,
    google,
    groq,
    openai,
    pydantic_ai,
    simple,
)
from marimo._dependencies.dependencies import DependencyManager


@pytest.fixture
def mock_openai_client():
    """Fixture for mocking the OpenAI client."""
    with patch("openai.OpenAI") as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Setup the streaming response structure
        mock_chunk = MagicMock()
        mock_choice = MagicMock()
        mock_delta = MagicMock()
        mock_delta.content = "Test response"
        mock_choice.delta = mock_delta
        mock_chunk.choices = [mock_choice]

        # Return an iterable for streaming
        mock_client.chat.completions.create.return_value = [mock_chunk]

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
    with patch("google.genai.Client") as mock_google_class:
        mock_client = MagicMock()
        mock_google_class.return_value = mock_client

        # Setup the response structure
        mock_response = MagicMock()
        mock_response.text = "Test response"
        mock_client.models.generate_content.return_value = mock_response

        yield mock_client, mock_google_class


@pytest.fixture
def mock_azure_openai_client():
    """Fixture for mocking the Azure OpenAI client."""
    with patch("openai.AzureOpenAI") as mock_azure_openai_class:
        mock_client = MagicMock()
        mock_azure_openai_class.return_value = mock_client

        # Setup the streaming response structure
        mock_chunk = MagicMock()
        mock_choice = MagicMock()
        mock_delta = MagicMock()
        mock_delta.content = "Test response"
        mock_choice.delta = mock_delta
        mock_chunk.choices = [mock_choice]

        # Return an iterable for streaming
        mock_client.chat.completions.create.return_value = [mock_chunk]

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
    model = google("gemini-2.5-flash-preview-05-20")
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

        result_gen = model(test_messages, test_config)
        # Consume the generator to get the final result
        result = list(result_gen)[-1] if result_gen else ""

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
        assert call_args["messages"][0]["content"] == [
            {"type": "text", "text": DEFAULT_SYSTEM_MESSAGE}
        ]
        assert call_args["messages"][1]["role"] == "user"
        assert call_args["messages"][1]["content"] == [
            {"type": "text", "text": "Test prompt"}
        ]
        assert call_args["max_completion_tokens"] == 100
        # Use pytest.approx for floating point comparisons
        assert call_args["temperature"] == pytest.approx(0.7)
        assert call_args["top_p"] == pytest.approx(0.9)
        assert call_args["frequency_penalty"] == pytest.approx(0.5)
        assert call_args["presence_penalty"] == pytest.approx(0.5)

    def test_call_with_base_url(
        self, mock_openai_client, test_messages, test_config
    ):
        """Test calling the openai class with a custom base URL."""
        mock_client, mock_openai_class = mock_openai_client

        # Create model with API key and base URL
        model = openai(
            "gpt-4", api_key="test-key", base_url="https://example.com"
        )

        result_gen = model(test_messages, test_config)
        # Consume the generator to get the final result
        result = list(result_gen)[-1] if result_gen else ""

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

        result_gen = model(test_messages, test_config)
        # Consume the generator to get the final result
        result = list(result_gen)[-1] if result_gen else ""

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

        # For streaming, we need to mock a streaming response with no content
        # Create an empty chunk
        mock_chunk = MagicMock()
        mock_chunk.choices = []
        mock_client.chat.completions.create.return_value = [mock_chunk]

        # Create model with API key
        model = openai("gpt-4", api_key="test-key")

        result_gen = model(test_messages, test_config)
        # Consume the generator to get the final result
        result_list = list(result_gen)
        result = result_list[-1] if result_list else ""

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
                ChatMessage(
                    role="system",
                    content="Custom system",
                    parts=[TextPart(type="text", text="Custom system")],
                ),
                ChatMessage(
                    role="user",
                    content="Hello",
                    parts=[TextPart(type="text", text="Hello")],
                ),
                ChatMessage(
                    role="assistant",
                    content="Hi there",
                    parts=[TextPart(type="text", text="Hi there")],
                ),
                ChatMessage(
                    role="user",
                    content="How are you?",
                    parts=[TextPart(type="text", text="How are you?")],
                ),
            ]

            model(messages, ChatModelConfig())

            # Verify the messages were properly converted
            call_args = mock_client.chat.completions.create.call_args[1]
            assert len(call_args["messages"]) == 5  # system + all messages

            assert call_args["messages"] == [
                {
                    "role": "system",
                    "content": [
                        {"type": "text", "text": DEFAULT_SYSTEM_MESSAGE}
                    ],
                },
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "Custom system"}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello"}],
                },
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Hi there"}],
                },
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "How are you?"}],
                },
            ]


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
        model = google("gemini-2.5-flash-preview-05-20")
        assert model.model == "gemini-2.5-flash-preview-05-20"
        assert model.system_message == DEFAULT_SYSTEM_MESSAGE
        assert model.api_key is None

        model = google(
            "gemini-2.5-flash-preview-05-20",
            system_message="Custom system message",
            api_key="test-key",
        )
        assert model.model == "gemini-2.5-flash-preview-05-20"
        assert model.system_message == "Custom system message"
        assert model.api_key == "test-key"

    @patch.object(google, "_require_api_key")
    @patch("google.genai.Client")
    def test_call(
        self,
        mock_genai_client_class: MagicMock,
        mock_require_api_key: MagicMock,
    ) -> None:
        """Test calling the google class."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_genai_client_class.return_value = mock_client

        # Setup streaming response
        mock_chunk = MagicMock()
        mock_chunk.text = "Test response"
        mock_client.models.generate_content_stream.return_value = [mock_chunk]

        model = google("gemini-2.5-flash-preview-05-20")
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

            result_gen = model(messages, config)
            # Consume the generator to get the final result
            result = list(result_gen)[-1] if result_gen else ""
            assert result == "Test response"

            mock_genai_client_class.assert_called_once_with(api_key="test-key")

        mock_client.models.generate_content_stream.assert_called_once()
        call_args = mock_client.models.generate_content_stream.call_args[1]
        assert call_args["model"] == "gemini-2.5-flash-preview-05-20"
        config_arg = call_args["config"]
        assert config_arg["system_instruction"] == DEFAULT_SYSTEM_MESSAGE
        assert config_arg["max_output_tokens"] == 100
        assert config_arg["temperature"] == 0.7
        assert config_arg["top_p"] == 0.9
        assert config_arg["top_k"] == 10
        assert config_arg["frequency_penalty"] == 0.5
        assert config_arg["presence_penalty"] == 0.5

    @patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "env-key"})
    def test_require_api_key_env(self) -> None:
        """Test _require_api_key with environment variable."""
        model = google("gemini-2.5-flash-preview-05-20")
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

        model = google("gemini-2.5-flash-preview-05-20")
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

        model = google("gemini-2.5-flash-preview-05-20")
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

        # Setup streaming response using context manager
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=None)
        mock_stream.text_stream = ["Test response"]
        mock_client.messages.stream.return_value = mock_stream

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

            result_gen = model(messages, config)
            # Consume the generator to get the final result
            result = list(result_gen)[-1] if result_gen else ""
            assert result == "Test response"

            mock_anthropic_class.assert_called_once_with(
                api_key="test-key", base_url=None
            )
        mock_client.messages.stream.assert_called_once()
        call_args = mock_client.messages.stream.call_args[1]
        assert call_args["model"] == "claude-3-opus-20240229"
        assert call_args["system"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["max_tokens"] == 100
        assert call_args["temperature"] == 0.7
        assert call_args["top_p"] == 0.9
        assert call_args["top_k"] == 10

    @patch.object(anthropic, "_require_api_key")
    @patch("anthropic.Anthropic")
    def test_call_tool_use(
        self, mock_anthropic_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the anthropic class with tool use response.

        Note: With streaming API, tool use may not be supported in the same way.
        This test is kept for backwards compatibility but may need revision.
        """
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Setup streaming response with empty text (tool use case)
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=None)
        mock_stream.text_stream = []  # No text for tool use
        mock_client.messages.stream.return_value = mock_stream

        model = anthropic("claude-3-opus-20240229")
        messages = [ChatMessage(role="user", content="Test prompt")]
        config = ChatModelConfig()

        result_gen = model(messages, config)
        # Consume the generator
        result_list = list(result_gen)
        # For empty text stream, expect empty result
        result = result_list[-1] if result_list else ""
        assert result == ""

    @patch.object(anthropic, "_require_api_key")
    @patch("anthropic.Anthropic")
    def test_call_empty_content(
        self, mock_anthropic_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test calling the anthropic class with empty content."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Setup streaming response with no content
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=None)
        mock_stream.text_stream = []
        mock_client.messages.stream.return_value = mock_stream

        model = anthropic("claude-3-opus-20240229")
        messages = [ChatMessage(role="user", content="Test prompt")]
        config = ChatModelConfig()

        result_gen = model(messages, config)
        # Consume the generator
        result_list = list(result_gen)
        result = result_list[-1] if result_list else ""
        assert result == ""

    def test_supports_temperature(self) -> None:
        """Test supports_temperature method."""
        model = anthropic("claude-3-opus-20240229")
        assert model.supports_temperature("claude-3-opus-20240229") is True
        assert model.supports_temperature("claude-3-sonnet-20240229") is True
        assert model.supports_temperature("claude-3-haiku-20240307") is True

        # Reasoning models (>4.0) don't support temperature
        assert model.supports_temperature("claude-sonnet-4-5") is False
        assert model.supports_temperature("claude-opus-4-5") is False
        assert model.supports_temperature("claude-4-opus") is False

    @patch.object(anthropic, "_require_api_key")
    @patch("anthropic.Anthropic")
    def test_call_without_temperature_for_reasoning_model(
        self, mock_anthropic_class: MagicMock, mock_require_api_key: MagicMock
    ) -> None:
        """Test that temperature is not included for reasoning models."""
        mock_require_api_key.return_value = "test-key"
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        # Setup streaming response
        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=None)
        mock_stream.text_stream = ["Test response"]
        mock_client.messages.stream.return_value = mock_stream

        model = anthropic("claude-sonnet-4-5")
        messages = [ChatMessage(role="user", content="Test prompt")]
        config = ChatModelConfig(
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
            top_k=10,
        )

        result_gen = model(messages, config)
        list(result_gen)  # Consume the generator

        mock_client.messages.stream.assert_called_once()
        call_args = mock_client.messages.stream.call_args[1]
        assert call_args["model"] == "claude-sonnet-4-5"
        assert call_args["system"] == DEFAULT_SYSTEM_MESSAGE
        assert call_args["max_tokens"] == 100
        # Temperature should not be included for reasoning models
        assert "temperature" not in call_args
        assert call_args["top_p"] == 0.9
        assert call_args["top_k"] == 10

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

    @pytest.mark.xfail(
        reason="latest litellm and openai are not compatible",
    )
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


@pytest.mark.skipif(
    not DependencyManager.pydantic_ai.has(),
    reason="pydantic-ai is not installed",
)
class TestPydanticAI:
    """Tests for the pydantic_ai class."""

    def test_init_with_agent(self):
        """Test initialization with an Agent."""
        from pydantic_ai import Agent

        agent = Agent("openai:gpt-4.1", instructions="Test instructions")
        model = pydantic_ai(agent)

        assert model.agent is agent
        assert model.model_settings is None

    def test_init_with_agent_and_settings(self):
        """Test initialization with Agent and model settings."""
        from pydantic_ai import Agent
        from pydantic_ai.settings import ModelSettings

        agent = Agent("openai:gpt-4.1")
        settings = ModelSettings(max_tokens=1000, temperature=0.7)
        model = pydantic_ai(agent, model_settings=settings)

        assert model.agent is agent
        assert model.model_settings is settings
        assert model.model_settings.max_tokens == 1000
        assert model.model_settings.temperature == 0.7

    def test_call_returns_async_generator(self, test_messages, test_config):
        """Test that calling returns an async generator."""
        import inspect

        from pydantic_ai import Agent

        agent = Agent("openai:gpt-4.1")
        model = pydantic_ai(agent)
        result = model(test_messages, test_config)

        assert inspect.isasyncgen(result)

    def test_convert_messages_to_pydantic_ai(self):
        """Test message conversion to Pydantic AI format."""
        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelRequest, ModelResponse

        agent = Agent("openai:gpt-4.1")
        model = pydantic_ai(agent)

        messages = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there!"),
            ChatMessage(role="user", content="How are you?"),
        ]

        converted = model._convert_messages_to_pydantic_ai(messages)

        assert len(converted) == 3
        assert isinstance(converted[0], ModelRequest)
        assert isinstance(converted[1], ModelResponse)
        assert isinstance(converted[2], ModelRequest)

    def test_convert_messages_with_tool_parts(self):
        """Test message conversion with tool invocation parts."""
        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelRequest, ModelResponse

        agent = Agent("openai:gpt-4.1")
        model = pydantic_ai(agent)

        messages = [
            ChatMessage(role="user", content="What's the weather?"),
            ChatMessage(
                role="assistant",
                content="Let me check...",
                parts=[
                    {"type": "text", "text": "Let me check..."},
                    {
                        "type": "tool-get_weather",
                        "toolCallId": "call_123",
                        "state": "output-available",
                        "input": {"location": "SF"},
                        "output": {"temp": 72},
                    },
                ],
            ),
        ]

        converted = model._convert_messages_to_pydantic_ai(messages)

        assert len(converted) >= 2
        # First is user request
        assert isinstance(converted[0], ModelRequest)
        # Second should be response with tool call
        assert isinstance(converted[1], ModelResponse)

    def test_agent_with_tools(self):
        """Test creating a model with an Agent that has tools."""
        from pydantic_ai import Agent

        def my_tool(arg: str) -> str:
            """A test tool."""
            return arg

        agent = Agent("openai:gpt-4.1", tools=[my_tool])
        model = pydantic_ai(agent)

        assert model.agent is agent
        # Tools are stored on the agent, not the wrapper
        assert len(agent._function_tools) == 1

    def test_agent_with_anthropic_thinking_settings(self):
        """Test creating a model with Anthropic thinking settings."""
        from pydantic_ai import Agent
        from pydantic_ai.models.anthropic import AnthropicModelSettings

        agent = Agent("anthropic:claude-sonnet-4-5")
        settings = AnthropicModelSettings(
            max_tokens=8000,
            anthropic_thinking={"type": "enabled", "budget_tokens": 4000},
        )
        model = pydantic_ai(agent, model_settings=settings)

        assert model.model_settings is settings
        assert model.model_settings.anthropic_thinking == {
            "type": "enabled",
            "budget_tokens": 4000,
        }

    def test_extract_stored_pydantic_messages(self):
        """Test extraction of stored pydantic-ai messages from parts."""
        from pydantic_ai import Agent
        from pydantic_ai.messages import (
            ModelMessagesTypeAdapter,
            ModelRequest,
            ModelResponse,
            TextPart as PydanticTextPart,
            UserPromptPart,
        )

        agent = Agent("openai:gpt-4.1")
        model = pydantic_ai(agent)

        # Create some test messages and serialize them
        test_messages = [
            ModelRequest(parts=[UserPromptPart(content="Hello")]),
            ModelResponse(parts=[PydanticTextPart(content="Hi there!")]),
        ]
        messages_json = ModelMessagesTypeAdapter.dump_json(test_messages)

        # Create parts with stored history
        parts = [
            {"type": "text", "text": "Some response"},
            {
                "type": "_pydantic_history",
                "messages_json": messages_json.decode("utf-8"),
            },
        ]

        # Extract should find and deserialize the messages
        extracted = model._extract_stored_pydantic_messages(
            parts, ModelMessagesTypeAdapter
        )

        assert extracted is not None
        assert len(extracted) == 2
        assert isinstance(extracted[0], ModelRequest)
        assert isinstance(extracted[1], ModelResponse)

    def test_extract_stored_pydantic_messages_none_when_missing(self):
        """Test that extraction returns None when no stored history."""
        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelMessagesTypeAdapter

        agent = Agent("openai:gpt-4.1")
        model = pydantic_ai(agent)

        # Parts without _pydantic_history
        parts = [
            {"type": "text", "text": "Some response"},
            {"type": "reasoning", "text": "Some thinking"},
        ]

        extracted = model._extract_stored_pydantic_messages(
            parts, ModelMessagesTypeAdapter
        )

        assert extracted is None

    def test_convert_messages_uses_stored_history(self):
        """Test that message conversion uses stored pydantic history when available."""
        from pydantic_ai import Agent
        from pydantic_ai.messages import (
            ModelMessagesTypeAdapter,
            ModelRequest,
            ModelResponse,
            TextPart as PydanticTextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )

        agent = Agent("openai:gpt-4.1")
        model = pydantic_ai(agent)

        # Create properly paired tool messages
        stored_messages = [
            ModelRequest(
                parts=[UserPromptPart(content="What's the weather?")]
            ),
            ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="get_weather",
                        args={"location": "SF"},
                        tool_call_id="call_123",
                    ),
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="get_weather",
                        content='{"temp": 72}',
                        tool_call_id="call_123",
                    ),
                ]
            ),
            ModelResponse(
                parts=[PydanticTextPart(content="The weather is 72F")]
            ),
        ]
        messages_json = ModelMessagesTypeAdapter.dump_json(stored_messages)

        # Create chat messages with stored history
        messages = [
            ChatMessage(role="user", content="What's the weather?"),
            ChatMessage(
                role="assistant",
                content="The weather is 72F",
                parts=[
                    {"type": "text", "text": "The weather is 72F"},
                    {
                        "type": "_pydantic_history",
                        "messages_json": messages_json.decode("utf-8"),
                    },
                ],
            ),
            ChatMessage(role="user", content="Thanks!"),
        ]

        converted = model._convert_messages_to_pydantic_ai(messages)

        # Should have: 4 stored messages + 1 new user message = 5
        assert len(converted) == 5
        # Last should be the new user message
        assert isinstance(converted[4], ModelRequest)
        assert converted[4].parts[0].content == "Thanks!"


class TestChatMessagePartConversion:
    """Tests for ChatMessage part conversion (unknown parts pass through)."""

    def test_unknown_part_types_pass_through(self):
        """Test that unknown part types are kept as-is instead of discarded."""
        # Create a message with a custom/unknown part type
        msg = ChatMessage(
            role="assistant",
            content="Test",
            parts=[
                {"type": "text", "text": "Hello"},
                {"type": "_pydantic_history", "messages_json": "[]"},
                {"type": "unknown_custom_type", "data": "some data"},
            ],
        )

        # All parts should be preserved
        assert len(msg.parts) == 3

        # The unknown parts should still be accessible as dicts
        pydantic_history_part = None
        for part in msg.parts:
            if (
                isinstance(part, dict)
                and part.get("type") == "_pydantic_history"
            ):
                pydantic_history_part = part
                break

        assert pydantic_history_part is not None
        assert pydantic_history_part["messages_json"] == "[]"
