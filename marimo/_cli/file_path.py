# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json
import logging
import os
import pathlib
import urllib.parse
import urllib.request
from tempfile import TemporaryDirectory
from typing import Optional

import click

from marimo._cli.print import green
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


def validate_name(
    name: str, allow_new_file: bool
) -> tuple[str, Optional[TemporaryDirectory[str]]]:
    """
    Validate the name of the file to be edited/run.

    If its an existing path, check that it is a valid Python file.
    If its a URL, we download it to a temporary file and return
    the path to that file.

    Args:
        name: The name of the file to be edited/run.

    Returns:
        The name of file to to be edited/run
        Optional TemporaryDirectory, returned to prevent it from being
          cleaned up
    """

    if _is_github_issue_url(name):
        temp_dir = TemporaryDirectory()
        return _handle_github_issue(name, temp_dir), temp_dir

    path = pathlib.Path(name)
    if path.suffix == ".ipynb":
        prefix = str(path)[: -len(".ipynb")]
        raise click.UsageError(
            f"Invalid NAME - {name} is not a Python file.\n\n"
            f"  {green('Tip:')} Convert {name} to a marimo notebook with\n\n"
            f"    marimo convert {name} > {prefix}.py\n\n"
            f"  then open with marimo edit {prefix}.py"
        )
    elif path.suffix != ".py":
        raise click.UsageError("Invalid NAME - %s is not a Python file" % name)

    if is_github_src(name, ext=".py"):
        temp_dir = TemporaryDirectory()
        return _handle_github_src(name, temp_dir), temp_dir

    if is_url(name):
        temp_dir = TemporaryDirectory()
        return _create_tmp_file_from_url(name, temp_dir), temp_dir

    if not allow_new_file:
        if not os.path.exists(name):
            raise click.UsageError("Invalid NAME - %s does not exist" % name)
        if not path.is_file():
            raise click.UsageError("Invalid NAME - %s is not a file" % name)

    return name, None


def _is_github_issue_url(url: str) -> bool:
    return is_url(url) and url.startswith(
        "https://github.com/marimo-team/marimo/issues/"
    )


def _handle_github_issue(url: str, temp_dir: TemporaryDirectory[str]) -> str:
    issue_number = url.split("/")[-1]
    api_url = f"https://api.github.com/repos/marimo-team/marimo/issues/{issue_number}"
    issue_response = urllib.request.urlopen(api_url).read().decode("utf-8")
    issue_json = json.loads(issue_response)
    body = issue_json["body"]

    # Find the content between first ```python and last ```
    try:
        code = _find_python_code_in_github_issue(body)
    except IndexError:
        raise click.UsageError(
            "Invalid Issue - %s does not include a marimo app" % url
        ) from None

    # Create a temporary file with the content
    path_to_app = _create_tmp_file_from_content(
        code, f"issue_{issue_number}.py", temp_dir
    )
    return path_to_app


def _find_python_code_in_github_issue(body: str) -> str:
    # Find the content between first ```python and last ```
    return body.split("```python")[1].rsplit("```", 1)[0]


def _handle_github_src(url: str, temp_dir: TemporaryDirectory[str]) -> str:
    url = get_github_src_url(url)
    path_to_app = _create_tmp_file_from_url(url, temp_dir)
    return path_to_app


def _create_tmp_file_from_url(
    url: str, temp_dir: TemporaryDirectory[str]
) -> str:
    logging.info("Downloading %s", url)
    path_to_app = os.path.join(temp_dir.name, os.path.basename(url))
    urllib.request.urlretrieve(url=url, filename=path_to_app)
    logging.info("App saved to %s", path_to_app)
    return path_to_app


def _create_tmp_file_from_content(
    content: str, name: str, temp_dir: TemporaryDirectory[str]
) -> str:
    logging.info("Creating temporary file")
    path_to_app = os.path.join(temp_dir.name, name)
    with open(path_to_app, "w") as f:
        f.write(content)
    logging.info("App saved to %s", path_to_app)
    return path_to_app
