# Copyright 2024 Marimo. All rights reserved.
import tempfile
from typing import Any
from unittest.mock import mock_open, patch

import click
import pytest

from marimo._cli.file_path import (
    _create_tmp_file_from_content,
    _create_tmp_file_from_url,
    _find_python_code_in_github_issue,
    _handle_github_issue,
    _is_github_issue_url,
    is_github_src,
    validate_name,
)

temp_dir = tempfile.TemporaryDirectory()


def test_validate_name_with_python_file() -> None:
    full_path = __file__
    assert validate_name(
        full_path, allow_new_file=False, allow_directory=False
    )[0].endswith("test_file_path.py")


def test_validate_name_with_non_python_file() -> None:
    with pytest.raises(click.UsageError):
        validate_name(
            "example.txt", allow_new_file=False, allow_directory=False
        )
    with pytest.raises(click.UsageError):
        validate_name(
            "example.txt", allow_new_file=True, allow_directory=False
        )


def test_validate_name_with_nonexistent_file() -> None:
    with pytest.raises(click.UsageError):
        validate_name(
            "nonexistent.py", allow_new_file=False, allow_directory=False
        )
    assert (
        "nonexistent.py"
        == validate_name(
            "nonexistent.py", allow_new_file=True, allow_directory=False
        )[0]
    )


def test_validate_name_with_directory_false() -> None:
    with pytest.raises(click.UsageError):
        validate_name(".", allow_new_file=False, allow_directory=False)
    with pytest.raises(click.UsageError):
        validate_name(".", allow_new_file=True, allow_directory=False)


def test_validate_name_with_directory_true() -> None:
    assert (
        "."
        == validate_name(".", allow_new_file=False, allow_directory=True)[0]
    )
    assert (
        "." == validate_name(".", allow_new_file=True, allow_directory=True)[0]
    )


def test_is_github_issue_url_with_valid_url() -> None:
    valid_url = "https://github.com/marimo-team/marimo/issues/1"
    assert _is_github_issue_url(valid_url) is True

    invalid_url = "https://github.com/marimo-team/marimo/pull/1"
    assert _is_github_issue_url(invalid_url) is False


def test_is_github_src_with_valid_url() -> None:
    valid_url = "https://github.com/marimo-team/marimo/blob/main/example.py"
    assert is_github_src(valid_url, ext=".py") is True

    invalid_url = "https://github.com/marimo-team/marimo/blob/main/example.txt"
    assert is_github_src(invalid_url, ext=".py") is False


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
    result = _handle_github_issue(issue_url, temp_dir)

    # Check if the result is a path to a temporary file
    assert result.endswith(".py")
    assert open(result).read().strip() == "print('Hello, world!')"


def test_create_tmp_file_from_url() -> None:
    url = "https://raw.githubusercontent.com/marimo-team/marimo/main/examples/optimization/regularization_and_sparsity.py"
    result = _create_tmp_file_from_url(url, temp_dir)

    # Check if the result is a path to a temporary file
    assert result.endswith(".py")


def test_create_tmp_file_from_content() -> None:
    content = 'print("Hello, world!")'
    name = "test_script.py"
    result = _create_tmp_file_from_content(content, name, temp_dir)

    assert result.endswith(name)
    assert open(result).read() == content


def test_find_python_code_in_github_issue_multiple_codes() -> None:
    body = """
    some text.
    ```python
    print("First block of Python code")
    ```
    some more text.
    ```python
    print("Second block of Python code")
    ```
    """
    expected = '\n    print("First block of Python code")\n    '
    actual = _find_python_code_in_github_issue(body)
    assert actual == expected

    body = """
    some text without any code blocks.
    """
    try:
        _find_python_code_in_github_issue(body)
        raise AssertionError("Expected an IndexError")
    except IndexError:
        # IndexError if there are no code blocks
        pass

    body = """
    some text.
    ```python
    print("Only one block of Python code")
    ```
    """
    expected = '\n    print("Only one block of Python code")\n    '
    actual = _find_python_code_in_github_issue(body)
    assert actual == expected
