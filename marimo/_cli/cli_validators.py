# Copyright 2024 Marimo. All rights reserved.
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
