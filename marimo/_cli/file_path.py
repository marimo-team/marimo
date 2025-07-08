# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import os
import re
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional, cast
from urllib.error import HTTPError

import marimo._utils.requests as requests
from marimo import _loggers
from marimo._cli.print import green
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.url import is_url

LOGGER = _loggers.marimo_logger()

USER_AGENT_HEADER = {"User-Agent": requests.MARIMO_USER_AGENT}


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
    def read(self, name: str) -> tuple[str, str]:
        """Read the file and return its content and filename."""
        pass


class LocalFileReader(FileReader):
    def can_read(self, name: str) -> bool:
        return not is_url(name)

    def read(self, name: str) -> tuple[str, str]:
        file_path = Path(name)
        # Is directory
        if file_path.is_dir():
            return "", file_path.name
        content = file_path.read_text(encoding="utf-8")
        return content, file_path.name


class GitHubIssueReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_url(name) and name.startswith(
            "https://github.com/marimo-team/marimo/issues/"
        )

    def read(self, name: str) -> tuple[str, str]:
        issue_number = name.split("/")[-1]
        api_url = f"https://api.github.com/repos/marimo-team/marimo/issues/{issue_number}"
        response = requests.get(api_url)
        response.raise_for_status()
        issue_response = cast(dict[str, Any], response.json())

        if "body" not in issue_response:
            raise ValueError(
                f"Failed to read GitHub issue {name}. No 'body' in response {issue_response}"
            )

        body = issue_response["body"]
        code = self._find_python_code_in_github_issue(body)
        return code, f"issue_{issue_number}.py"

    @staticmethod
    def _find_python_code_in_github_issue(body: str) -> str:
        if "```python" not in body:
            raise ValueError(f"No Python code found in GitHub issue {body}")

        return body.split("```python")[1].rsplit("```", 1)[0]


class StaticNotebookReader(FileReader):
    CODE_TAG = r"marimo-code"
    CODE_REGEX = re.compile(r"<marimo-code\s+hidden(?:=['\"]{2})?\s*>(.*?)<")
    FILENAME_REGEX = re.compile(
        r"<marimo-filename\s+hidden(?:=['\"]{2})?\s*>(.*?)<"
    )

    def can_read(self, name: str) -> bool:
        return self._is_static_marimo_notebook_url(name)[0]

    def read(self, name: str) -> tuple[str, str]:
        _, file_contents = self._is_static_marimo_notebook_url(name)
        code = self._extract_code_from_static_notebook(file_contents)
        filename = self._extract_filename_from_static_notebook(file_contents)
        return code, filename

    @staticmethod
    def _is_static_marimo_notebook_url(url: str) -> tuple[bool, str]:
        def download(url: str) -> tuple[bool, str]:
            LOGGER.info("Downloading %s", url)
            response = requests.get(url, headers=USER_AGENT_HEADER)
            response.raise_for_status()
            file_contents = response.text()
            return (
                StaticNotebookReader.CODE_TAG in file_contents,
                file_contents,
            )

        # Not a URL
        if not is_url(url):
            return False, ""

        # Ends with .html, try to download it
        if url.endswith(".html"):
            return download(url)

        # Starts with https://static.marimo.app/, append /download
        if url.startswith("https://static.marimo.app/static"):
            normalized_url = url if url.endswith("/") else url + "/"
            return download(urllib.parse.urljoin(normalized_url, "download"))

        # Other marimo domains
        DOMAINS = [
            "marimo.app",
            "links.marimo.app",
        ]
        if any(url.startswith(f"https://{domain}/") for domain in DOMAINS):
            return download(url)

        # TODO: Adjust for other various forms of static marimo notebook URLs.
        if "notebooks/nb" in url:
            return download(url)

        # Otherwise, not a static marimo notebook
        return False, ""

    @staticmethod
    def _extract_code_from_static_notebook(file_contents: str) -> str:
        search = re.search(StaticNotebookReader.CODE_REGEX, file_contents)
        assert search is not None, "<marimo-code> not found in file contents"
        return urllib.parse.unquote(search.group(1))

    @staticmethod
    def _extract_filename_from_static_notebook(file_contents: str) -> str:
        if search := re.search(
            StaticNotebookReader.FILENAME_REGEX, file_contents
        ):
            return urllib.parse.unquote(search.group(1))
        return "notebook.py"


class GitHubSourceReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_github_src(name, ext=".py") or is_github_src(name, ext=".md")

    def read(self, name: str) -> tuple[str, str]:
        url = get_github_src_url(name)
        response = requests.get(url, headers=USER_AGENT_HEADER)
        response.raise_for_status()
        content = response.text()
        return content, os.path.basename(url)


class GenericURLReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_url(name)

    def read(self, name: str) -> tuple[str, str]:
        response = requests.get(name, headers=USER_AGENT_HEADER)
        response.raise_for_status()
        content = response.text()
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

    def read_file(self, name: str) -> tuple[str, str]:
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
    ) -> tuple[str, Optional[TemporaryDirectory[str]]]:
        pass


class LocalFileHandler(FileHandler):
    def __init__(self, allow_new_file: bool, allow_directory: bool):
        self.allow_new_file = allow_new_file
        self.allow_directory = allow_directory

    def can_handle(self, name: str) -> bool:
        return not is_url(name)

    def handle(
        self, name: str, temp_dir: TemporaryDirectory[str]
    ) -> tuple[str, Optional[TemporaryDirectory[str]]]:
        del temp_dir
        import click

        path = Path(name)

        if self.allow_directory and path.is_dir():
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
            if not path.exists():
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
    ) -> tuple[str, Optional[TemporaryDirectory[str]]]:
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
        LOGGER.info("Creating temporary file")
        path_to_app = Path(temp_dir.name) / name
        # If doesn't end in .py, add it
        if not path_to_app.suffix == ".py":
            path_to_app = path_to_app.with_suffix(".py")
        path_to_app.write_text(content, encoding="utf-8")
        LOGGER.info("App saved to %s", path_to_app)
        return str(path_to_app)


def validate_name(
    name: str, allow_new_file: bool, allow_directory: bool
) -> tuple[str, Optional[TemporaryDirectory[str]]]:
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
