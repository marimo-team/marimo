# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
import urllib.error
from unittest.mock import mock_open, patch

import click
import pytest

from marimo._cli.file_path import (
    FileContentReader,
    GenericURLReader,
    GitHubIssueReader,
    GitHubSourceReader,
    LocalFileReader,
    StaticNotebookReader,
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
    with pytest.raises(click.ClickException):
        validate_name(
            "example.txt", allow_new_file=False, allow_directory=False
        )
    with pytest.raises(click.ClickException):
        validate_name(
            "example.txt", allow_new_file=True, allow_directory=False
        )


def test_validate_name_with_nonexistent_file() -> None:
    with pytest.raises(click.ClickException):
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
    with pytest.raises(click.ClickException):
        validate_name(".", allow_new_file=False, allow_directory=False)
    with pytest.raises(click.ClickException):
        validate_name(".", allow_new_file=True, allow_directory=False)


def test_validate_name_with_directory_true() -> None:
    assert (
        "."
        == validate_name(".", allow_new_file=False, allow_directory=True)[0]
    )
    assert (
        "." == validate_name(".", allow_new_file=True, allow_directory=True)[0]
    )


def test_github_issue_reader() -> None:
    reader = GitHubIssueReader()
    valid_url = "https://github.com/marimo-team/marimo/issues/1"
    invalid_url = "https://github.com/marimo-team/marimo/pull/1"

    assert reader.can_read(valid_url) is True
    assert reader.can_read(invalid_url) is False

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock_open(
            read_data=b"""{
                "body": "Some content.```python\\nprint('Hello, world!')\\n```"}
            """  # noqa: E501
        )
        mock_urlopen.return_value = mock_response()

        content, filename = reader.read(valid_url)
        assert content.strip() == "print('Hello, world!')"
        assert filename == "issue_1.py"


def test_is_github_src_with_valid_url() -> None:
    valid_url = "https://github.com/marimo-team/marimo/blob/main/example.py"
    assert is_github_src(valid_url, ext=".py") is True

    invalid_url = "https://github.com/marimo-team/marimo/blob/main/example.txt"
    assert is_github_src(invalid_url, ext=".py") is False


def test_github_source_reader() -> None:
    reader = GitHubSourceReader()
    valid_url = "https://github.com/marimo-team/marimo/blob/main/example.py"
    invalid_url = "https://github.com/marimo-team/marimo/blob/main/example.txt"

    assert reader.can_read(valid_url) is True
    assert reader.can_read(invalid_url) is False

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock_open(read_data=b"print('Hello, world!')")
        mock_urlopen.return_value = mock_response()

        content, filename = reader.read(valid_url)
        assert content == "print('Hello, world!')"
        assert filename == "example.py"


def test_local_file_reader() -> None:
    reader = LocalFileReader()
    assert reader.can_read("local_file.py") is True
    assert reader.can_read("https://example.com/file.py") is False

    with patch("builtins.open", mock_open(read_data="print('Hello, world!')")):
        content, filename = reader.read("local_file.py")
        assert content == "print('Hello, world!')"
        assert filename == "local_file.py"


def test_static_notebook_reader() -> None:
    reader = StaticNotebookReader()
    valid_url = "https://static.marimo.app/example"
    invalid_url = "https://example.com/file.py"

    with patch.object(
        StaticNotebookReader, "_is_static_marimo_notebook_url"
    ) as mock_is_static:
        mock_is_static.return_value = (
            True,
            "<marimo-code hidden=''>print('Hello')</marimo-code><marimo-filename hidden=''>test.py</marimo-filename>",  # noqa: E501
        )
        assert reader.can_read(valid_url) is True
        content, filename = reader.read(valid_url)
        assert content == "print('Hello')"
        assert filename == "test.py"

        mock_is_static.return_value = (False, "")
        assert reader.can_read(invalid_url) is False


def test_generic_url_reader() -> None:
    reader = GenericURLReader()
    assert reader.can_read("https://example.com/file.py") is True
    assert reader.can_read("local_file.py") is False

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock_open(read_data=b"print('Hello, world!')")
        mock_urlopen.return_value = mock_response()

        content, filename = reader.read("https://example.com/file.py")
        assert content == "print('Hello, world!')"
        assert filename == "file.py"


def test_file_content_reader() -> None:
    reader = FileContentReader()

    with (
        patch.object(LocalFileReader, "read") as mock_local_read,
        patch.object(GitHubIssueReader, "read") as mock_github_issue_read,
        patch.object(
            StaticNotebookReader, "read"
        ) as mock_static_notebook_read,
        patch.object(GitHubSourceReader, "read") as mock_github_source_read,
        patch.object(GenericURLReader, "read") as mock_generic_url_read,
    ):
        mock_local_read.return_value = ("local content", "local.py")
        mock_github_issue_read.return_value = ("issue content", "issue.py")
        mock_static_notebook_read.return_value = (
            "notebook content",
            "notebook.py",
        )
        mock_github_source_read.return_value = ("github content", "github.py")
        mock_generic_url_read.return_value = ("url content", "url.py")

        assert reader.read_file("local.py") == ("local content", "local.py")
        assert reader.read_file(
            "https://github.com/marimo-team/marimo/issues/1"
        ) == ("issue content", "issue.py")
        assert reader.read_file(
            "https://github.com/marimo-team/marimo/blob/main/example.py"
        ) == ("github content", "github.py")
        assert reader.read_file("https://example.com/file.py") == (
            "url content",
            "url.py",
        )

    with pytest.raises((FileNotFoundError, OSError)):
        reader.read_file("invalid://example.com")


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
    actual = GitHubIssueReader._find_python_code_in_github_issue(body)
    assert actual == expected

    body = """
    some text without any code blocks.
    """
    try:
        GitHubIssueReader._find_python_code_in_github_issue(body)
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
    actual = GitHubIssueReader._find_python_code_in_github_issue(body)
    assert actual == expected


def test_validate_name_with_invalid_extension():
    with pytest.raises(click.ClickException):
        validate_name(
            "file.invalid", allow_new_file=True, allow_directory=False
        )


def test_validate_name_with_markdown_file():
    assert (
        validate_name("file.md", allow_new_file=True, allow_directory=False)[0]
        == "file.md"
    )


def test_validate_name_with_jupyter_notebook():
    with pytest.raises(click.ClickException) as excinfo:
        validate_name(
            "notebook.ipynb", allow_new_file=True, allow_directory=False
        )
    assert "Convert notebook.ipynb to a marimo notebook" in str(excinfo.value)


def test_generic_url_reader_with_query_params():
    reader = GenericURLReader()
    url = "https://example.com/file.py?param=value"
    assert reader.can_read(url) is True
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = mock_open(read_data=b"print('Hello, world!')")
        mock_urlopen.return_value = mock_response()
        content, filename = reader.read(url)
        assert content == "print('Hello, world!')"
        assert filename == "file.py"


def test_static_notebook_reader_url_formats():
    reader = StaticNotebookReader()
    urls = [
        "https://static.marimo.app/example",
        "https://static.marimo.app/example/",
        "https://static.marimo.app/example.html",
    ]
    for url in urls:
        with patch.object(
            StaticNotebookReader, "_is_static_marimo_notebook_url"
        ) as mock_is_static:
            mock_is_static.return_value = (
                True,
                "<marimo-code hidden=''>print('Hello')</marimo-code><marimo-filename hidden=''>test.py</marimo-filename>",  # noqa: E501
            )
            assert reader.can_read(url) is True
            content, filename = reader.read(url)
            assert content == "print('Hello')"
            assert filename == "test.py"


def test_github_issue_reader_nonexistent_issue():
    reader = GitHubIssueReader()
    url = "https://github.com/marimo-team/marimo/issues/999999"  # noqa: E501
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url,
            404,
            "Not Found",
            {},  # ignore
            None,
        )
        with pytest.raises(urllib.error.HTTPError):
            reader.read(url)


def test_github_source_reader_different_extensions():
    reader = GitHubSourceReader()
    urls = [
        "https://github.com/marimo-team/marimo/blob/main/example.py",
        "https://github.com/marimo-team/marimo/blob/main/README.md",
    ]
    for url in urls:
        assert reader.can_read(url) is True
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = mock_open(read_data=b"content")
            mock_urlopen.return_value = mock_response()
            content, filename = reader.read(url)
            assert content == "content"
            assert filename in ["example.py", "README.md"]


def test_local_file_reader_with_spaces():
    reader = LocalFileReader()
    filename = "file with spaces.py"
    assert reader.can_read(filename) is True
    with patch("builtins.open", mock_open(read_data="print('Hello, world!')")):
        content, read_filename = reader.read(filename)
        assert content == "print('Hello, world!')"
        assert read_filename == filename


def test_validate_name_with_relative_and_absolute_paths():
    relative_path = "relative/path/file.py"
    absolute_path = "/absolute/path/file.py"

    with (
        patch("os.path.exists", return_value=True),
        patch("pathlib.Path.is_file", return_value=True),
    ):
        assert (
            validate_name(
                relative_path, allow_new_file=False, allow_directory=False
            )[0]
            == relative_path
        )
        assert (
            validate_name(
                absolute_path, allow_new_file=False, allow_directory=False
            )[0]
            == absolute_path
        )
