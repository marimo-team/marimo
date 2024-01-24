# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional

from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc


@mddoc
def doc(obj: Any) -> Optional[Html]:
    """Get documentation about an object.

    If the object implements the `RichHelp` protocol, the documentation will be
    rendered as markdown.

    **Args.**

    - `obj`: The object to get documentation about.

    **Returns.**

    - Documentation as an `Html` object if the object implements `RichHelp`;
      otherwise, documentation is printed to console (and nothing is returned)
    """
    if hasattr(obj, "_rich_help_"):
        msg = obj._rich_help_()
        return (
            md(msg) if msg is not None else md("No documentation available.")
        )
    else:
        help(obj)
        return None
