# Copyright 2026 Marimo. All rights reserved.
"""Resolve browser-visible package indexes for WASM exports."""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.parse
from typing import TYPE_CHECKING

from marimo._utils.inline_script_metadata import PyProjectReader

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._utils.marimo_path import MarimoPath


def resolve_pypi_index_urls(
    path: MarimoPath,
    explicit: Sequence[str],
) -> tuple[str, ...]:
    """Resolve simple pip/uv indexes without embedding credentials in HTML."""
    if explicit:
        return tuple(explicit)

    urls: list[str] = []
    try:
        reader = PyProjectReader.from_filename(path.absolute_name)
        if reader.index_url:
            urls.append(reader.index_url)
        urls.extend(reader.extra_index_urls)
    except Exception:
        pass

    if urls:
        return tuple(dict.fromkeys(urls))

    for key in ("global.index-url", "global.extra-index-url"):
        try:
            pip = shutil.which("pip")
            command = (
                [pip, "config", "get", key]
                if pip
                else [
                    "python",
                    "-m",
                    "pip",
                    "config",
                    "get",
                    key,
                ]
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0:
            urls.extend(
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            )

    if urls:
        return tuple(dict.fromkeys(urls))

    for name in ("UV_INDEX_URL", "PIP_INDEX_URL"):
        value = os.environ.get(name)
        if value:
            urls.append(value)
            break
    for name in ("UV_EXTRA_INDEX_URL", "PIP_EXTRA_INDEX_URL"):
        value = os.environ.get(name)
        if value:
            urls.extend(value.split())

    if not urls:
        urls.append("https://pypi.org/simple/")
    return tuple(dict.fromkeys(urls))


def public_pypi_index_urls(urls: Sequence[str]) -> tuple[str, ...]:
    """Remove URL credentials before package indexes enter exported HTML."""
    sanitized: list[str] = []
    for value in urls:
        parsed = urllib.parse.urlsplit(value)
        if not parsed.username and not parsed.password:
            sanitized.append(value)
            continue
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        sanitized.append(
            urllib.parse.urlunsplit(
                (
                    parsed.scheme,
                    host,
                    parsed.path,
                    parsed.query,
                    parsed.fragment,
                )
            )
        )
    return tuple(dict.fromkeys(sanitized))
