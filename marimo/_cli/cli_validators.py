# Copyright 2024 Marimo. All rights reserved.
from typing import Any

import click


def start_with_slash(ctx: Any, param: Any, value: str) -> str:
    del ctx
    del param
    if not value.startswith("/"):
        raise click.BadParameter("Must start with /")
    return value
