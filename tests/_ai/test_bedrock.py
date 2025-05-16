# Copyright 2024 Marimo. All rights reserved.

import json
import unittest
from unittest.mock import MagicMock, patch

import pytest

from marimo._ai._types import ChatMessage, ChatModelConfig
from marimo._ai.llm._impl import bedrock


class TestBedrockModelClass(unittest.TestCase):
    """Test the Bedrock model class"""

    def test_init(self):
        """Test initialization of the bedrock model class"""
        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            system_message="Test system message",
            region_name="us-east-1",
        )

        assert model.model == "anthropic.claude-3-sonnet-20240229"
        assert model.system_message == "Test system message"
        assert model.region_name == "us-east-1"
        assert model.profile_name is None
        assert model.credentials is None

    def test_init_with_credentials(self):
        """Test initialization with explicit credentials"""
        credentials = {
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
        }
        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            credentials=credentials,
        )

        assert model.credentials == credentials

    def test_init_with_profile(self):
        """Test initialization with AWS profile"""
        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            profile_name="test-profile",
        )

        assert model.profile_name == "test-profile"


class TestBedrockClientCreation(unittest.TestCase):
    """Test Bedrock client creation with different authentication methods"""

    @patch("boto3.client")
    def test_default_client_creation(self, mock_client):
        """Test client creation with default settings"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        model = bedrock("anthropic.claude-3-sonnet-20240229")
        client = model._get_bedrock_client()

        mock_client.assert_called_once_with(
            "bedrock-runtime", region_name="us-east-1"
        )
        assert client == mock_client_instance

    @patch("boto3.client")
    def test_client_with_credentials(self, mock_client):
        """Test client creation with explicit credentials"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        credentials = {
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
        }

        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            credentials=credentials,
        )
        client = model._get_bedrock_client()

        mock_client.assert_called_once_with(
            "bedrock-runtime",
            region_name="us-east-1",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            aws_session_token=None,
        )
        assert client == mock_client_instance

    @patch("boto3.Session")
    def test_client_with_profile(self, mock_session):
        """Test client creation with AWS profile"""
        mock_session_instance = MagicMock()
        mock_client_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.client.return_value = mock_client_instance

        model = bedrock(
            "anthropic.claude-3-sonnet-20240229",
            profile_name="test-profile",
        )
        client = model._get_bedrock_client()

        mock_session.assert_called_once_with(profile_name="test-profile")
        mock_session_instance.client.assert_called_once_with(
            "bedrock-runtime", region_name="us-east-1"
        )
        assert client == mock_client_instance


class TestBedrockRequestPreparation(unittest.TestCase):
    """Test Bedrock request preparation for different providers"""

    def test_anthropic_request_preparation(self):
        """Test preparation of Anthropic (Claude) request body"""
        model = bedrock("anthropic.claude-3-sonnet-20240229")

        messages = [ChatMessage(role="user", content="Hello, Claude!")]

        config = ChatModelConfig(
            temperature=0.7,
            max_tokens=100,
        )

        request_body = model._prepare_anthropic_request(messages, config)

        assert request_body["system"] == model.system_message
        assert len(request_body["messages"]) == 1
        assert request_body["messages"][0]["role"] == "user"
        assert request_body["temperature"] == 0.7
        assert request_body["max_tokens"] == 100

    def test_meta_request_preparation(self):
        """Test preparation of Meta (Llama) request body"""
        model = bedrock("meta.llama3-8b-instruct-v1:0")

        messages = [
            ChatMessage(role="user", content="Hello Llama!"),
            ChatMessage(
                role="assistant", content="Hello! How can I assist you?"
            ),
            ChatMessage(role="user", content="What's the capital of France?"),
        ]

        config = ChatModelConfig(
            temperature=0.8,
            max_tokens=200,
        )

        request_body = model._prepare_meta_request(messages, config)

        assert request_body["prompt"].startswith(model.system_message)
        assert "Human: Hello Llama!" in request_body["prompt"]
        assert (
            "Assistant: Hello! How can I assist you?" in request_body["prompt"]
        )
        assert "Human: What's the capital of France?" in request_body["prompt"]
        assert request_body["temperature"] == 0.8
        assert request_body["max_gen_len"] == 200

    def test_amazon_request_preparation(self):
        """Test preparation of Amazon Titan request body"""
        model = bedrock("amazon.titan-text-express-v1")

        messages = [
            ChatMessage(role="user", content="Hello Titan!"),
            ChatMessage(
                role="assistant", content="Hello! How can I assist you?"
            ),
            ChatMessage(role="user", content="What's the capital of France?"),
        ]

        config = ChatModelConfig(
            temperature=0.8,
            max_tokens=200,
        )

        request_body = model._prepare_amazon_request(messages, config)

        assert request_body["inputText"].startswith(model.system_message)
        assert "User: Hello Titan!" in request_body["inputText"]
        assert (
            "Assistant: Hello! How can I assist you?"
            in request_body["inputText"]
        )
        assert (
            "User: What's the capital of France?" in request_body["inputText"]
        )
        assert request_body["textGenerationConfig"]["temperature"] == 0.8
        assert request_body["textGenerationConfig"]["maxTokenCount"] == 200


class TestBedrockResponseHandling(unittest.TestCase):
    """Test Bedrock response handling for different providers"""

    def test_anthropic_response_parsing(self):
        """Test parsing of Anthropic (Claude) response"""
        model = bedrock("anthropic.claude-3-sonnet-20240229")

        # Mock response
        mock_response = {
            "body": MagicMock(),
        }
        mock_response["body"].read.return_value = json.dumps(
            {
                "content": [
                    {"type": "text", "text": "Paris is the capital of France."}
                ]
            }
        )

        # Parse response
        result = model._parse_response(mock_response, "anthropic")

        assert result == "Paris is the capital of France."

    def test_meta_response_parsing(self):
        """Test parsing of Meta (Llama) response"""
        model = bedrock("meta.llama3-8b-instruct-v1:0")

        # Mock response
        mock_response = {
            "body": MagicMock(),
        }
        mock_response["body"].read.return_value = json.dumps(
            {"generation": "Paris is the capital of France."}
        )

        # Parse response
        result = model._parse_response(mock_response, "meta")

        assert result == "Paris is the capital of France."

    def test_amazon_response_parsing(self):
        """Test parsing of Amazon Titan response"""
        model = bedrock("amazon.titan-text-express-v1")

        # Mock response
        mock_response = {
            "body": MagicMock(),
        }
        mock_response["body"].read.return_value = json.dumps(
            {"outputText": "Paris is the capital of France."}
        )

        # Parse response
        result = model._parse_response(mock_response, "amazon")

        assert result == "Paris is the capital of France."


class TestBedrockCallMethod(unittest.TestCase):
    """Test the __call__ method of the Bedrock model"""

    @patch.object(bedrock, "_get_bedrock_client")
    @patch.object(bedrock, "_prepare_request_body")
    @patch.object(bedrock, "_parse_response")
    def test_call_method(self, mock_parse, mock_prepare, mock_get_client):
        """Test the __call__ method"""
        # Setup mocks
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_prepare.return_value = {"test": "request"}
        mock_parse.return_value = "Test response"

        mock_response = {"body": MagicMock()}
        mock_client.invoke_model.return_value = mock_response

        # Create model and make call
        model = bedrock("anthropic.claude-3-sonnet-20240229")
        messages = [ChatMessage(role="user", content="Test message")]
        config = ChatModelConfig()

        result = model(messages, config)

        # Verify results
        mock_get_client.assert_called_once()
        mock_prepare.assert_called_once_with(messages, config, "anthropic")
        mock_client.invoke_model.assert_called_once_with(
            modelId="anthropic.claude-3-sonnet-20240229",
            body=json.dumps({"test": "request"}),
            contentType="application/json",
            accept="application/json",
        )
        mock_parse.assert_called_once_with(mock_response, "anthropic")
        assert result == "Test response"

    def test_invalid_model_id(self):
        """Test error handling with invalid model ID"""
        model = bedrock("invalid-model")

        with pytest.raises(ValueError) as context:
            model(
                [ChatMessage(role="user", content="Hello")], ChatModelConfig()
            )

        assert "Invalid model ID format" in str(context.value)


if __name__ == "__main__":
    unittest.main()
