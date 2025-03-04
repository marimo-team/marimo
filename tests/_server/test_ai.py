# Copyright 2024 Marimo. All rights reserved.
import unittest
from unittest.mock import Mock

from marimo._server.api.endpoints.ai import get_content


class TestGetContent(unittest.TestCase):
    def test_get_content_with_none_delta(self) -> None:
        # Create a mock response with choices but delta is None
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].delta = None
        
        # Ensure text attribute doesn't exist to avoid fallback
        type(mock_response).text = property(lambda self: None)

        # Call get_content with the mock response
        result = get_content(mock_response)

        # Assert that the result is None
        self.assertIsNone(result)

    def test_get_content_with_delta_content(self) -> None:
        # Create a mock response with choices and delta.content
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].delta = Mock()
        mock_response.choices[0].delta.content = "Test content"

        # Call get_content with the mock response
        result = get_content(mock_response)

        # Assert that the result is the expected content
        self.assertEqual(result, "Test content")
