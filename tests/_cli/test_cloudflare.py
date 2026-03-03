# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import tempfile
from unittest.mock import patch

import click
import pytest

from marimo._cli.files.cloudflare import (
    R2FileHandler,
    _download_r2_object,
    parse_r2_path,
)
from marimo._cli.files.file_path import validate_name


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("r2://bucket/file.py", ("bucket", "file.py")),
        ("r2://bucket/path/to/file.py", ("bucket", "path/to/file.py")),
    ],
)
def test_parse_r2_path(url: str, expected: tuple[str, str]) -> None:
    assert parse_r2_path(url) == expected


@pytest.mark.parametrize(
    ("url", "match"),
    [
        ("r2://bucket/", "Missing object key"),
        ("r2://bucket", "Expected format"),
        ("https://example.com", "Not an r2:// URL"),
    ],
)
def test_parse_r2_path_errors(url: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_r2_path(url)


class TestR2FileHandler:
    def test_can_handle(self) -> None:
        handler = R2FileHandler()
        assert handler.can_handle("r2://bucket/file.py") is True
        assert handler.can_handle("https://example.com") is False
        assert handler.can_handle("file.py") is False

    @patch("marimo._cli.files.cloudflare._download_r2_object")
    def test_handle(self, mock_download, tmp_path) -> None:
        handler = R2FileHandler()
        temp_dir = tempfile.TemporaryDirectory(dir=tmp_path)

        mock_download.side_effect = lambda _bucket, _key, local_path: open(
            local_path, "w"
        ).close()

        path, returned_temp_dir = handler.handle(
            "r2://my-bucket/notebooks/test.py", temp_dir
        )

        assert path.endswith("test.py")
        assert returned_temp_dir is temp_dir
        mock_download.assert_called_once_with(
            "my-bucket", "notebooks/test.py", path
        )


@patch(
    "marimo._cli.files.cloudflare.shutil.which",
    return_value="/usr/bin/npx",
)
@patch("marimo._cli.files.cloudflare.subprocess.run")
def test_download_calls_wrangler(mock_run, mock_which) -> None:
    del mock_which
    mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)

    _download_r2_object("my-bucket", "path/to/file.py", "/tmp/file.py")

    mock_run.assert_called_once_with(
        [
            "npx",
            "wrangler",
            "r2",
            "object",
            "get",
            "my-bucket/path/to/file.py",
            "--file",
            "/tmp/file.py",
            "--remote",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@patch(
    "marimo._cli.files.cloudflare.shutil.which",
    return_value="/usr/bin/npx",
)
@patch("marimo._cli.files.cloudflare.subprocess.run")
def test_download_wrangler_failure(mock_run, mock_which) -> None:
    del mock_which
    mock_run.side_effect = subprocess.CalledProcessError(
        returncode=1,
        cmd=["npx", "wrangler"],
        stderr="authentication required",
    )

    with pytest.raises(click.ClickException, match="Failed to download r2://"):
        _download_r2_object("bucket", "key.py", "/tmp/key.py")


@patch("marimo._cli.files.cloudflare.shutil.which", return_value=None)
def test_download_npx_not_found(mock_which) -> None:
    del mock_which
    with pytest.raises(click.ClickException, match="npx is not available"):
        _download_r2_object("bucket", "key.py", "/tmp/key.py")


@patch("marimo._cli.files.cloudflare._download_r2_object")
def test_validate_name_routes_to_r2(mock_download) -> None:
    mock_download.side_effect = lambda _bucket, _key, local_path: open(
        local_path, "w"
    ).close()

    path, temp_dir = validate_name(
        "r2://my-bucket/notebook.py",
        allow_new_file=False,
        allow_directory=False,
    )

    assert path.endswith("notebook.py")
    assert temp_dir is not None
    mock_download.assert_called_once_with("my-bucket", "notebook.py", path)
    temp_dir.cleanup()
