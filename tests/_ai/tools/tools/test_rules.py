# Copyright 2025 Marimo. All rights reserved.

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.rules import GetMarimoRules
from marimo._ai._tools.types import EmptyArgs


@pytest.fixture
def tool() -> GetMarimoRules:
    """Create a GetMarimoRules tool instance."""
    return GetMarimoRules(ToolContext())


def test_get_rules_from_bundled_file(tool: GetMarimoRules) -> None:
    """Test successfully loading marimo rules from the bundled file."""
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = "# Marimo Rules\n\nBundled content"

    with patch("marimo._ai._tools.tools.rules.MARIMO_RULES_PATH", mock_path):
        result = tool.handle(EmptyArgs())

    assert result.status == "success"
    assert result.rules_content == "# Marimo Rules\n\nBundled content"
    assert result.source_url == "bundled"
    assert len(result.next_steps) == 1
    assert "Follow the guidelines" in result.next_steps[0]
    mock_path.exists.assert_called_once()
    mock_path.read_text.assert_called_once_with(encoding="utf-8")


def test_get_rules_bundled_file_read_error_fallback_to_url(
    tool: GetMarimoRules,
) -> None:
    """Test falling back to URL when bundled file exists but can't be read."""
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.side_effect = OSError("Permission denied")

    mock_response = Mock()
    mock_response.text.return_value = "# Marimo Rules\n\nURL content"
    mock_response.raise_for_status = Mock()

    with (
        patch("marimo._ai._tools.tools.rules.MARIMO_RULES_PATH", mock_path),
        patch("marimo._utils.requests.get", return_value=mock_response),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "success"
    assert result.rules_content == "# Marimo Rules\n\nURL content"
    assert result.source_url == "https://docs.marimo.io/CLAUDE.md"
    mock_path.exists.assert_called_once()
    mock_path.read_text.assert_called_once_with(encoding="utf-8")
    mock_response.raise_for_status.assert_called_once()


def test_get_rules_success(tool: GetMarimoRules) -> None:
    """Test successfully fetching marimo rules from URL when bundled file doesn't exist."""
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = False

    mock_response = Mock()
    mock_response.text.return_value = "# Marimo Rules\n\nTest content"
    mock_response.raise_for_status = Mock()

    with (
        patch("marimo._ai._tools.tools.rules.MARIMO_RULES_PATH", mock_path),
        patch("marimo._utils.requests.get", return_value=mock_response),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "success"
    assert result.rules_content == "# Marimo Rules\n\nTest content"
    assert result.source_url == "https://docs.marimo.io/CLAUDE.md"
    assert len(result.next_steps) == 1
    assert "Follow the guidelines" in result.next_steps[0]
    mock_path.exists.assert_called_once()
    mock_response.raise_for_status.assert_called_once()


def test_get_rules_http_error(tool: GetMarimoRules) -> None:
    """Test handling HTTP errors when fetching rules from URL."""
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = False

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("404 Not Found")

    with (
        patch("marimo._ai._tools.tools.rules.MARIMO_RULES_PATH", mock_path),
        patch("marimo._utils.requests.get", return_value=mock_response),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "error"
    assert result.rules_content is None
    assert "Failed to fetch marimo rules" in result.message
    assert "404 Not Found" in result.message
    assert result.source_url == "https://docs.marimo.io/CLAUDE.md"
    assert len(result.next_steps) == 3
    assert "Check internet connectivity" in result.next_steps[0]


def test_get_rules_network_error(tool: GetMarimoRules) -> None:
    """Test handling network errors when fetching rules from URL."""
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = False

    with (
        patch("marimo._ai._tools.tools.rules.MARIMO_RULES_PATH", mock_path),
        patch(
            "marimo._utils.requests.get",
            side_effect=Exception("Connection refused"),
        ),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "error"
    assert result.rules_content is None
    assert "Failed to fetch marimo rules" in result.message
    assert "Connection refused" in result.message
    assert len(result.next_steps) == 3


def test_get_rules_timeout(tool: GetMarimoRules) -> None:
    """Test handling timeout when fetching rules from URL."""
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = False

    with (
        patch("marimo._ai._tools.tools.rules.MARIMO_RULES_PATH", mock_path),
        patch(
            "marimo._utils.requests.get",
            side_effect=Exception("Request timeout"),
        ),
    ):
        result = tool.handle(EmptyArgs())

    assert result.status == "error"
    assert result.rules_content is None
    assert "Request timeout" in result.message
