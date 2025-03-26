# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import abc
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent
from typing import Optional
from urllib.error import HTTPError

from marimo import _loggers
from marimo._ast import codegen
from marimo._ast.app import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._cli.print import green
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.url import is_url

LOGGER = _loggers.marimo_logger()


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
    """Base class for file readers that handle different file types and sources."""

    @abc.abstractmethod
    def can_read(self, name: str) -> bool:
        """Check if this reader can handle the given file.

        Args:
            name: File path or URL

        Returns:
            bool: True if this reader can handle the file
        """
        pass

    @abc.abstractmethod
    def read(self, name: str) -> tuple[str, str]:
        """Read the file and return its content and filename."""
        pass


class LocalFileReader(FileReader):
    def can_read(self, name: str) -> bool:
        if is_url(name):
            return False
        path = Path(name)
        return path.is_dir() or MarimoPath.is_valid_path(name)

    def read(self, name: str) -> tuple[str, str]:
        file_path = Path(name)
        # Is directory
        if file_path.is_dir():
            return "", file_path.name
        content = file_path.read_text(encoding="utf-8")
        return content, file_path.name


class IPYNBFileReader(FileReader):
    def can_read(self, name: str) -> bool:
        return Path(name).suffix == ".ipynb"

    def read(self, name: str) -> tuple[str, str]:
        # This doesn't actually, but rather prints a helpful error.
        import click

        path = Path(name)
        without_suffix = path.stem
        raise click.ClickException(
            f"Invalid NAME - {name} is not a Python file.\n\n"
            f"  {green('Tip:')} Convert {name} to a marimo notebook with"
            "\n\n"
            f"    marimo convert {name} > {without_suffix}.py\n\n"
            f"  then open with marimo edit {without_suffix}.py"
        )


class DataFileReader(FileReader):
    EXTENSIONS = {".csv", ".parquet", ".json", ".jsonl"}

    def can_read(self, name: str) -> bool:
        # Remote data files not supported yet
        if is_url(name):
            return False

        return Path(name).suffix in self.EXTENSIONS

    def read(self, name: str) -> tuple[str, str]:
        path = Path(name)
        method = {
            ".csv": "scan_csv",
            ".parquet": "scan_parquet",
            ".json": "scan_json",
            ".jsonl": "scan_ndjson",
        }[path.suffix]

        # For simplicity, we are a bit opinionated and opt
        # for polars
        cell_code = f"""
        import polars as pl
        df = pl.{method}(r"{name}")
        df.head(10).collect()
        """

        app_code = codegen.generate_filecontents(
            [dedent(cell_code)],
            ["_"],
            [CellConfig()],
            _AppConfig(width="medium"),
        )
        return app_code, f"data_{path.stem}.py"


class SQLFileReader(FileReader):
    EXTENSIONS = {".sql", ".sqlite", ".db", ".duckdb"}

    def can_read(self, name: str) -> bool:
        # Remote SQL files not supported yet
        if is_url(name):
            return False

        return Path(name).suffix in self.EXTENSIONS

    def read(self, name: str) -> tuple[str, str]:
        path = Path(name)

        cell_code = f'''
        df = mo.sql(f"""
        ATTACH '{name}' AS db (TYPE sqlite)
        """)
        '''

        cells = ["import marimo as mo\nimport duckdb", dedent(cell_code)]
        app_code = codegen.generate_filecontents(
            ["import marimo as mo", dedent(cell_code)],
            ["_"] * len(cells),
            [CellConfig()] * len(cells),
            _AppConfig(width="medium"),
        )
        return app_code, f"sql_{path.stem}.py"


class GitHubIssueReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_url(name) and name.startswith(
            "https://github.com/marimo-team/marimo/issues/"
        )

    def read(self, name: str) -> tuple[str, str]:
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

    def read(self, name: str) -> tuple[str, str]:
        _, file_contents = self._is_static_marimo_notebook_url(name)
        code = self._extract_code_from_static_notebook(file_contents)
        filename = self._extract_filename_from_static_notebook(file_contents)
        return code, filename

    @staticmethod
    def _is_static_marimo_notebook_url(url: str) -> tuple[bool, str]:
        def download(url: str) -> tuple[bool, str]:
            LOGGER.info("Downloading %s", url)
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

    def read(self, name: str) -> tuple[str, str]:
        url = get_github_src_url(name)
        content = urllib.request.urlopen(url).read().decode("utf-8")
        return content, os.path.basename(url)


class GenericURLReader(FileReader):
    def can_read(self, name: str) -> bool:
        return is_url(name)

    def read(self, name: str) -> tuple[str, str]:
        content = urllib.request.urlopen(name).read().decode("utf-8")
        # Remove query parameters from the URL
        url_without_query = name.split("?")[0]
        return content, os.path.basename(url_without_query)


class FileContentReader:
    def __init__(self) -> None:
        self.readers = [
            LocalFileReader(),
            DataFileReader(),
            SQLFileReader(),
            IPYNBFileReader(),
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


class NotebookOrDirectoryFileHandler(FileHandler):
    def __init__(self, allow_new_file: bool, allow_directory: bool):
        self.allow_new_file = allow_new_file
        self.allow_directory = allow_directory

    def can_handle(self, name: str) -> bool:
        # Must be local
        # Must be a directory or marimo file
        if is_url(name):
            return False
        return Path(name).is_dir() or MarimoPath.is_valid_path(name)

    def handle(
        self, name: str, temp_dir: TemporaryDirectory[str]
    ) -> tuple[str, Optional[TemporaryDirectory[str]]]:
        del temp_dir
        import click

        path = Path(name)

        if self.allow_directory and path.is_dir():
            return name, None

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


class TempNotebookFileHandler(FileHandler):
    """
    Handles URLs and data files (csv, parquet, json, etc.)
    """

    def __init__(self) -> None:
        self.reader = FileContentReader()

    def can_handle(self, name: str) -> bool:
        del name
        # Just attempt to run through all readers
        return True

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
        NotebookOrDirectoryFileHandler(allow_new_file, allow_directory),
        TempNotebookFileHandler(),
    ]

    temp_dir = TemporaryDirectory()

    for handler in handlers:
        if handler.can_handle(name):
            return handler.handle(name, temp_dir)

    raise ValueError(f"Unable to handle file {name}")
