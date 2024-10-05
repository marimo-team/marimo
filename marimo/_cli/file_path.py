# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import json
import logging
import os
import pathlib
import urllib.parse
import urllib.request
from tempfile import TemporaryDirectory
from typing import Optional, Tuple
from urllib.error import HTTPError

from marimo._cli.print import green
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.url import is_url


def is_github_src(url: str, ext: str) -> bool:
    if not is_url(url):
        return False

    hostname = urllib.parse.urlparse(url).hostname
    if hostname != "github.com" and hostname != "raw.githubusercontent.com":
        return False
    path: str = urllib.parse.urlparse(url).path
    if not path.endswith(ext):
        return False
    return True


def get_github_src_url(url: str) -> str:
    # Change hostname to raw.githubusercontent.com
    path = urllib.parse.urlparse(url).path
    path = path.replace("/blob/", "/", 1)
    return f"https://raw.githubusercontent.com{path}"


class FileReader(abc.ABC):
    @abc.abstractmethod
    def can_read(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    def read(self, name: str) -> Tuple[str, str]:
        """Read the file and return its content and filename."""
        pass


class LocalFileReader(FileReader):
    def can_read(self, name: str) -> bool:
        return not is_url(name)

    def read(self, name: str) -> Tuple[str, str]:
        # Is directory
        if os.path.isdir(name):
            return "", os.path.basename(name)
        with open(name, "r") as f:
            content = f.read()
        return content, os.path.basename(name)


class GitHubIssueReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_url(name) and name.startswith(
            "https://github.com/marimo-team/marimo/issues/"
        )

    def read(self, name: str) -> Tuple[str, str]:
        issue_number = name.split("/")[-1]
        api_url = f"https://api.github.com/repos/marimo-team/marimo/issues/{issue_number}"
        issue_response = urllib.request.urlopen(api_url).read().decode("utf-8")
        issue_json = json.loads(issue_response)
        body = issue_json["body"]
        code = self._find_python_code_in_github_issue(body)
        return code, f"issue_{issue_number}.py"

    @staticmethod
    def _find_python_code_in_github_issue(body: str) -> str:
        return body.split("```python")[1].rsplit("```", 1)[0]


class StaticNotebookReader(FileReader):
    CODE_PREFIX = '<marimo-code hidden="">'
    CODE_SUFFIX = "</marimo-code>"
    FILENAME_PREFIX = '<marimo-filename hidden="">'
    FILENAME_SUFFIX = "</marimo-filename>"

    def can_read(self, name: str) -> bool:
        return self._is_static_marimo_notebook_url(name)[0]

    def read(self, name: str) -> Tuple[str, str]:
        _, file_contents = self._is_static_marimo_notebook_url(name)
        code = self._extract_code_from_static_notebook(file_contents)
        filename = self._extract_filename_from_static_notebook(file_contents)
        return code, filename

    @staticmethod
    def _is_static_marimo_notebook_url(url: str) -> tuple[bool, str]:
        def download(url: str) -> tuple[bool, str]:
            logging.info("Downloading %s", url)
            request = urllib.request.Request(
                url,
                # User agent to avoid 403 Forbidden some bot protection
                headers={"User-Agent": "Mozilla/5.0"},
            )
            file_contents = (
                urllib.request.urlopen(request).read().decode("utf-8")
            )
            return StaticNotebookReader.CODE_PREFIX in file_contents, str(
                file_contents
            )

        # Not a URL
        if not is_url(url):
            return False, ""

        # Ends with .html, try to download it
        if url.endswith(".html"):
            return download(url)

        # Starts with https://static.marimo.app/, append /download
        if url.startswith("https://static.marimo.app/"):
            return download(os.path.join(url, "download"))

        # Otherwise, not a static marimo notebook
        return False, ""

    @staticmethod
    def _extract_code_from_static_notebook(file_contents: str) -> str:
        # normalize hidden attribute
        file_contents = file_contents.replace("hidden=''", 'hidden=""')
        return file_contents.split(StaticNotebookReader.CODE_PREFIX)[1].split(
            StaticNotebookReader.CODE_SUFFIX
        )[0]

    @staticmethod
    def _extract_filename_from_static_notebook(file_contents: str) -> str:
        # normalize hidden attribute
        file_contents = file_contents.replace("hidden=''", 'hidden=""')
        return file_contents.split(StaticNotebookReader.FILENAME_PREFIX)[
            1
        ].split(StaticNotebookReader.FILENAME_SUFFIX)[0]


class GitHubSourceReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_github_src(name, ext=".py") or is_github_src(name, ext=".md")

    def read(self, name: str) -> Tuple[str, str]:
        url = get_github_src_url(name)
        content = urllib.request.urlopen(url).read().decode("utf-8")
        return content, os.path.basename(url)


class GenericURLReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_url(name)

    def read(self, name: str) -> Tuple[str, str]:
        content = urllib.request.urlopen(name).read().decode("utf-8")
        # Remove query parameters from the URL
        url_without_query = name.split("?")[0]
        return content, os.path.basename(url_without_query)


class FileContentReader:
    def __init__(self) -> None:
        self.readers = [
            LocalFileReader(),
            GitHubIssueReader(),
            StaticNotebookReader(),
            GitHubSourceReader(),
            GenericURLReader(),
        ]

    def read_file(self, name: str) -> Tuple[str, str]:
        """
        Read the file and return its content and filename

        Args:
            name (str): File path or URL

        Raises:
            ValueError: If the file cannot be read

        Returns:
            Tuple[str, str]: File content and filename
        """
        for reader in self.readers:
            if reader.can_read(name):
                return reader.read(name)
        raise ValueError(f"Unable to read file contents of {name}")


class FileHandler(abc.ABC):
    @abc.abstractmethod
    def can_handle(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    def handle(
        self, name: str, temp_dir: TemporaryDirectory[str]
    ) -> Tuple[str, Optional[TemporaryDirectory[str]]]:
        pass


class LocalFileHandler(FileHandler):
    def __init__(self, allow_new_file: bool, allow_directory: bool):
        self.allow_new_file = allow_new_file
        self.allow_directory = allow_directory

    def can_handle(self, name: str) -> bool:
        return not is_url(name)

    def handle(
        self, name: str, temp_dir: TemporaryDirectory[str]
    ) -> Tuple[str, Optional[TemporaryDirectory[str]]]:
        del temp_dir
        import click

        path = pathlib.Path(name)

        if self.allow_directory and os.path.isdir(name):
            return name, None

        if path.suffix == ".ipynb":
            prefix = str(path)[: -len(".ipynb")]
            raise click.ClickException(
                f"Invalid NAME - {name} is not a Python file.\n\n"
                f"  {green('Tip:')} Convert {name} to a marimo notebook with"
                "\n\n"
                f"    marimo convert {name} > {prefix}.py\n\n"
                f"  then open with marimo edit {prefix}.py"
            )

        if not MarimoPath.is_valid_path(path):
            raise click.ClickException(
                f"Invalid NAME - {name} is not a Python or Markdown file"
            )

        if not self.allow_new_file:
            if not os.path.exists(name):
                raise click.ClickException(
                    f"Invalid NAME - {name} does not exist"
                )
            if not path.is_file():
                raise click.ClickException(
                    f"Invalid NAME - {name} is not a file"
                )

        return name, None


class RemoteFileHandler(FileHandler):
    def __init__(self) -> None:
        self.reader = FileContentReader()

    def can_handle(self, name: str) -> bool:
        return is_url(name)

    def handle(
        self, name: str, temp_dir: TemporaryDirectory[str]
    ) -> Tuple[str, Optional[TemporaryDirectory[str]]]:
        try:
            content, filename = self.reader.read_file(name)
        except HTTPError as e:
            import click

            raise click.ClickException(f"Failed to read URL: {e}")  # noqa: B904
        path_to_app = self._create_tmp_file_from_content(
            content, filename, temp_dir
        )
        return path_to_app, temp_dir

    @staticmethod
    def _create_tmp_file_from_content(
        content: str, name: str, temp_dir: TemporaryDirectory[str]
    ) -> str:
        logging.info("Creating temporary file")
        path_to_app = os.path.join(temp_dir.name, name)
        with open(path_to_app, "w") as f:
            f.write(content)
        logging.info("App saved to %s", path_to_app)
        return path_to_app


def validate_name(
    name: str, allow_new_file: bool, allow_directory: bool
) -> Tuple[str, Optional[TemporaryDirectory[str]]]:
    """
    Validate the file name and return the path to the file.

    Args:
        name (str): Local file path, URL, or directory path
        allow_new_file (bool): Whether to allow creating a new file
        allow_directory (bool): Whether to allow a directory

    Raises:
        ValueError: If the file name is invalid

    Returns:
        Path to the file and temporary directory
    """
    handlers = [
        LocalFileHandler(allow_new_file, allow_directory),
        RemoteFileHandler(),
    ]

    temp_dir = TemporaryDirectory()

    for handler in handlers:
        if handler.can_handle(name):
            return handler.handle(name, temp_dir)

    raise ValueError(f"Unable to handle file {name}")
