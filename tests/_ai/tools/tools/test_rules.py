# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.rules import GetMarimoRules
from marimo._ai._tools.types import EmptyArgs


@pytest.fixture
def tool() -> GetMarimoRules:
    """Create a GetMarimoRules tool instance."""
    return GetMarimoRules(ToolContext())


def test_get_rules_success(tool: GetMarimoRules) -> None:
    """Test successfully fetching marimo rules."""
    mock_response = Mock()
    mock_response.text.return_value = "# Marimo Rules\n\nTest content"
    mock_response.raise_for_status = Mock()

    with patch("marimo._utils.requests.get", return_value=mock_response):
        result = tool.handle(EmptyArgs())

    assert result.status == "success"
    assert result.rules_content == "# Marimo Rules\n\nTest content"
    assert result.source_url == "https://docs.marimo.io/CLAUDE.md"
    assert len(result.next_steps) == 1
    assert "Follow the guidelines" in result.next_steps[0]
    mock_response.raise_for_status.assert_called_once()


def test_get_rules_http_error(tool: GetMarimoRules) -> None:
    """Test handling HTTP errors when fetching rules."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")

    with patch("marimo._utils.requests.get", return_value=mock_response):
        result = tool.handle(EmptyArgs())

    assert result.status == "error"
    assert result.rules_content is None
    assert "Failed to fetch marimo rules" in result.message
    assert "404 Not Found" in result.message
    assert result.source_url == "https://docs.marimo.io/CLAUDE.md"
    assert len(result.next_steps) == 3
    assert "Check internet connectivity" in result.next_steps[0]


def test_get_rules_network_error(tool: GetMarimoRules) -> None:
    """Test handling network errors when fetching rules."""
    with patch(
        "marimo._utils.requests.get",
        side_effect=Exception("Connection refused"),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "error"
    assert result.rules_content is None
    assert "Failed to fetch marimo rules" in result.message
    assert "Connection refused" in result.message
    assert len(result.next_steps) == 3


def test_get_rules_timeout(tool: GetMarimoRules) -> None:
    """Test handling timeout when fetching rules."""
    with patch(
        "marimo._utils.requests.get",
        side_effect=Exception("Request timeout"),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "error"
    assert result.rules_content is None
    assert "Request timeout" in result.message
