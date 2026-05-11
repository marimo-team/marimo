# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import click


def check_proxy_base_url(proxy: str | None, base_url_value: str) -> str:
    """Reconcile --proxy path with --base-url. Returns the effective
    base_url: explicit --base-url if given, else the path component from
    --proxy, else empty. Raises click.BadParameter when both are given
    and disagree (after trailing-slash normalization).
    """
    if not proxy:
        return base_url_value
    parse_target = proxy if "://" in proxy else f"//{proxy}"
    try:
        proxy_path = urlparse(parse_target).path
    except ValueError:
        return base_url_value
    proxy_path = proxy_path.rstrip("/")
    if not proxy_path:
        return base_url_value
    if base_url_value and proxy_path != base_url_value.rstrip("/"):
        raise click.BadParameter(
            f"--proxy path {proxy_path!r} conflicts with --base-url "
            f"{base_url_value!r}; use one or make them match.",
            param_hint="--proxy",
        )
    return base_url_value or proxy_path


def base_url(ctx: Any, param: Any, value: str | None) -> str:
    del ctx
    del param
    if value is None or value == "":
        return ""

    if value == "/":
        raise click.BadParameter(
            "Must not be /. This is equivalent to not setting the base URL."
        )
    if not value.startswith("/"):
        raise click.BadParameter("Must start with /")
    if value.endswith("/"):
        raise click.BadParameter("Must not end with /")
    return value


def is_file_path(ctx: Any, param: Any, value: str | None) -> str:
    del ctx
    del param
    if not value:
        raise click.BadParameter("Must be a file path")
    if not Path(value).exists():
        raise click.BadParameter(f"File does not exist: {value}")
    if not Path(value).is_file():
        raise click.BadParameter(f"Not a file: {value}")
    return value
