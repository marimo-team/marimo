from unittest.mock import Mock, patch

from marimo._server.ai.ids import (
    AiModelId,
    AiProviderId,
    QualifiedModelId,
    ShortModelId,
    _guess_provider,
)


class TestAiModelId:
    def test_init(self):
        """Test AiModelId initialization."""
        model_id = AiModelId(
            provider=AiProviderId("openai"), model=ShortModelId("gpt-4")
        )
        assert model_id.provider == "openai"
        assert model_id.model == "gpt-4"

    def test_str_conversion(self):
        """Test string conversion returns qualified model ID."""
        model_id = AiModelId(
            provider=AiProviderId("anthropic"), model=ShortModelId("claude-3")
        )
        result = str(model_id)
        assert result == "anthropic/claude-3"
        assert isinstance(result, str)

    def test_repr(self):
        """Test repr returns proper representation."""
        model_id = AiModelId(
            provider=AiProviderId("google"), model=ShortModelId("gemini-pro")
        )
        result = repr(model_id)
        assert result == "AiModelId(provider=google, model=gemini-pro)"

    def test_from_model_valid_format(self):
        """Test from_model with valid provider/model format."""
        model_id = AiModelId.from_model("openai/gpt-4")
        assert model_id.provider == "openai"
        assert model_id.model == "gpt-4"

    def test_from_model_complex_model_name(self):
        """Test from_model with complex model names containing slashes."""
        model_id = AiModelId.from_model(
            "huggingface/microsoft/DialoGPT-medium"
        )
        assert model_id.provider == "huggingface"
        assert model_id.model == "microsoft/DialoGPT-medium"

    @patch("marimo._server.ai.ids.LOGGER")
    def test_from_model_invalid_format_openai(self, mock_logger: Mock):
        """Test from_model with invalid format - should guess OpenAI."""
        model_id = AiModelId.from_model("gpt-4")

        assert model_id.provider == "openai"
        assert model_id.model == "gpt-4"

        # Verify warning was logged
        mock_logger.warning.assert_any_call(
            "Invalid model ID: gpt-4. Model ID must be in the format <provider>/<model>"
        )
        mock_logger.warning.assert_any_call(
            "Guessing provider for gpt-4 as openai"
        )

    @patch("marimo._server.ai.ids.LOGGER")
    def test_from_model_invalid_format_anthropic(self, mock_logger: Mock):
        """Test from_model with invalid format - should guess Anthropic."""
        model_id = AiModelId.from_model("claude-3-opus")

        assert model_id.provider == "anthropic"
        assert model_id.model == "claude-3-opus"

        mock_logger.warning.assert_any_call(
            "Invalid model ID: claude-3-opus. Model ID must be in the format <provider>/<model>"
        )

    @patch("marimo._server.ai.ids.LOGGER")
    def test_from_model_invalid_format_google(self, mock_logger: Mock):
        del mock_logger
        """Test from_model with invalid format - should guess Google."""
        model_id = AiModelId.from_model("gemini-pro")

        assert model_id.provider == "google"
        assert model_id.model == "gemini-pro"

    @patch("marimo._server.ai.ids.LOGGER")
    def test_from_model_invalid_format_ollama_fallback(
        self, mock_logger: Mock
    ):
        del mock_logger
        """Test from_model with invalid format - should fallback to Ollama."""
        model_id = AiModelId.from_model("llama2")

        assert model_id.provider == "ollama"
        assert model_id.model == "llama2"


class TestGuessProvider:
    def test_guess_openai_gpt(self):
        """Test guessing OpenAI provider for GPT models."""
        assert _guess_provider("gpt-4") == "openai"
        assert _guess_provider("gpt-3.5-turbo") == "openai"
        assert _guess_provider("gpt-4o") == "openai"

    def test_guess_openai_o3(self):
        """Test guessing OpenAI provider for O3 models."""
        assert _guess_provider("o3-mini") == "openai"
        assert _guess_provider("o3-max") == "openai"

    def test_guess_openai_o1(self):
        """Test guessing OpenAI provider for O1 models."""
        assert _guess_provider("o1-preview") == "openai"
        assert _guess_provider("o1-mini") == "openai"

    def test_guess_anthropic_claude(self):
        """Test guessing Anthropic provider for Claude models."""
        assert _guess_provider("claude-3-opus") == "anthropic"
        assert _guess_provider("claude-3-sonnet") == "anthropic"
        assert _guess_provider("claude-3-haiku") == "anthropic"
        assert _guess_provider("claude-2") == "anthropic"

    def test_guess_google_gemini(self):
        """Test guessing Google provider for Gemini models."""
        assert _guess_provider("gemini-pro") == "google"
        assert _guess_provider("gemini-1.5-pro") == "google"
        assert _guess_provider("gemini-flash") == "google"

    def test_guess_google_google_prefix(self):
        """Test guessing Google provider for models with google prefix."""
        assert _guess_provider("google-palm") == "google"
        assert _guess_provider("google-bard") == "google"

    def test_guess_ollama_fallback(self):
        """Test fallback to Ollama for unknown models."""
        assert _guess_provider("llama2") == "ollama"
        assert _guess_provider("mistral") == "ollama"
        assert _guess_provider("codellama") == "ollama"
        assert _guess_provider("unknown-model") == "ollama"

    def test_guess_provider_edge_cases(self):
        """Test edge cases for provider guessing."""
        # Empty string
        assert _guess_provider("") == "ollama"

        # Models that might be ambiguous
        assert _guess_provider("gpt") == "openai"  # Starts with gpt
        assert _guess_provider("claude") == "anthropic"  # Starts with claude
        assert _guess_provider("gemini") == "google"  # Starts with gemini

        # Case sensitivity (should work as expected)
        assert (
            _guess_provider("GPT-4") == "ollama"
        )  # Doesn't start with lowercase "gpt"
        assert (
            _guess_provider("Claude-3") == "ollama"
        )  # Doesn't start with lowercase "claude"


class TestTypeAliases:
    def test_type_aliases_are_strings(self):
        """Test that type aliases behave as strings."""
        provider_id = AiProviderId("test-provider")
        qualified_id = QualifiedModelId("test/model")
        short_id = ShortModelId("model")

        assert isinstance(provider_id, str)
        assert isinstance(qualified_id, str)
        assert isinstance(short_id, str)

        assert provider_id == "test-provider"
        assert qualified_id == "test/model"
        assert short_id == "model"
