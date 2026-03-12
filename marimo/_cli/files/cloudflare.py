# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import click

from marimo._cli.files.file_path import FileHandler

if TYPE_CHECKING:
    from tempfile import TemporaryDirectory


def is_r2_path(name: str) -> bool:
    return name.startswith("r2://")


def parse_r2_path(url: str) -> tuple[str, str]:
    """Parse an r2://bucket/key URL into (bucket, key).

    Raises ValueError if the URL is not a valid r2:// path.
    """
    if not is_r2_path(url):
        raise ValueError(f"Not an r2:// URL: {url}")

    path = url[len("r2://") :]
    if "/" not in path:
        raise ValueError(
            f"Invalid r2:// URL: {url}. Expected format: r2://bucket/key"
        )

    bucket, key = path.split("/", 1)
    if not key:
        raise ValueError(
            f"Invalid r2:// URL: {url}. Missing object key after bucket name"
        )

    return bucket, key


def _check_npx_available() -> None:
    if shutil.which("npx") is None:
        raise click.ClickException(
            "npx is not available on PATH. "
            "Install Node.js (https://nodejs.org) to use r2:// paths."
        )


def _download_r2_object(bucket: str, key: str, local_path: str) -> None:
    _check_npx_available()

    try:
        subprocess.run(
            [
                "npx",
                "wrangler",
                "r2",
                "object",
                "get",
                f"{bucket}/{key}",
                "--file",
                local_path,
                "--remote",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        msg = (
            f"Failed to download r2://{bucket}/{key}.\n\n"
            f"  wrangler stderr: {e.stderr.strip()}\n\n"
            "  Tip: run `npx wrangler login` to authenticate, "
            "or check that the bucket and key are correct."
        )
        raise click.ClickException(msg) from e


class R2FileHandler(FileHandler):
    def can_handle(self, name: str) -> bool:
        return is_r2_path(name)

    def handle(
        self, name: str, temp_dir: TemporaryDirectory[str]
    ) -> tuple[str, Optional[TemporaryDirectory[str]]]:
        bucket, key = parse_r2_path(name)
        filename = os.path.basename(key)
        local_path = str(Path(temp_dir.name) / filename)
        _download_r2_object(bucket, key, local_path)
        return local_path, temp_dir
