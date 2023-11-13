import os
from typing import Any
from unittest.mock import mock_open, patch

import click
import pytest

from marimo._cli.file_path import (
    _create_tmp_file_from_content,
    _create_tmp_file_from_url,
    _handle_github_issue,
    _handle_github_py,
    _is_github_issue_url,
    _is_github_py,
    validate_name,
)


def test_validate_name_with_python_file() -> None:
    full_path = __file__
    assert validate_name(full_path).endswith("test_file_path.py")


def test_validate_name_with_non_python_file() -> None:
    with pytest.raises(click.UsageError):
        validate_name("example.txt")


def test_validate_name_with_nonexistent_file() -> None:
    with pytest.raises(click.UsageError):
        validate_name("nonexistent.py")


def test_validate_name_with_directory() -> None:
    with pytest.raises(click.UsageError):
        validate_name(".")


def test_is_github_issue_url_with_valid_url() -> None:
    valid_url = "https://github.com/marimo-team/marimo/issues/1"
    assert _is_github_issue_url(valid_url) is True

    invalid_url = "https://github.com/marimo-team/marimo/pull/1"
    assert _is_github_issue_url(invalid_url) is False


def test_is_github_py_with_valid_url() -> None:
    valid_url = "https://github.com/marimo-team/marimo/blob/main/example.py"
    assert _is_github_py(valid_url) is True

    invalid_url = "https://github.com/marimo-team/marimo/blob/main/example.txt"
    assert _is_github_py(invalid_url) is False


@patch("urllib.request.urlopen")
def test_handle_github_issue(mock_urlopen: Any) -> None:
    # Mock the response from GitHub API
    mock_response = mock_open(
        read_data="""{
            "body": "Some content.```python\\nprint(\'Hello, world!\')\\n```"}
        """.encode()
    )
    mock_urlopen.return_value = mock_response()

    # Call the function with a mock URL
    issue_url = "https://github.com/marimo-team/marimo/issues/1"
    result = _handle_github_issue(issue_url)

    # Check if the result is a path to a temporary file
    assert result.endswith(".py")
    assert open(result).read() == "print('Hello, world!')"


def test_create_tmp_file_from_url():
    url = "https://raw.githubusercontent.com/marimo-team/marimo/main/examples/optimization/regularization_and_sparsity.py"
    result = _create_tmp_file_from_url(url)

    # Check if the result is a path to a temporary file
    assert result.endswith(".py")


def test_create_tmp_file_from_content():
    content = 'print("Hello, world!")'
    name = "test_script.py"
    result = _create_tmp_file_from_content(content, name)

    assert result.endswith("/test_script.py")
    assert open(result).read() == content
