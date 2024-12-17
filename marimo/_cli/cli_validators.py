# Copyright 2024 Marimo. All rights reserved.
from pathlib import Path
from typing import Any, Optional

import click


def base_url(ctx: Any, param: Any, value: Optional[str]) -> str:
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


def is_file_path(ctx: Any, param: Any, value: Optional[str]) -> str:
    del ctx
    del param
    if not value:
        raise click.BadParameter("Must be a file path")
    if not Path(value).exists():
        raise click.BadParameter(f"File does not exist: {value}")
    if not Path(value).is_file():
        raise click.BadParameter(f"Not a file: {value}")
    return value
