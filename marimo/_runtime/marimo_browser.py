# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import webbrowser

from marimo._runtime.context import get_context
from marimo._runtime.context.types import ContextNotInitializedError


def browser_open_fallback(
    url: str, new: int = 0, autoraise: bool = False
) -> bool:
    """
    Inserts an iframe with the given URL into the output.

    NB Returns false on failure.
    """
    import inspect

    import marimo as mo

    del new, autoraise  # unused

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return False

    if ctx.execution_context is None:
        return False

    # import antigravity is a real module in python. see:
    #    github.com/python/cpython/blob/main/Lib/antigravity.py
    # which automatically triggers a webbrowser.open call to the relevant
    # comic. We patch webbrowser.open due to an incompatible stub:
    #    https://pyodide.org/en/stable/usage/wasm-constraints.html
    # so may as well hook in to customize the easter egg. Especially since
    # iframe constraints actually block this from loading on marimo.app.
    #
    # For other python lore, try:
    #   import this
    stack = inspect.stack()
    if len(stack) > 3 and (
        stack[2].filename.endswith("antigravity.py")
        or (stack[1].filename.endswith("antigravity.py"))
    ):
        mo.output.append(
            mo.image(
                "https://marimo.app/images/antigravity.png",
                alt=(
                    "The image shows 2 stick figures in XKCD style. The one "
                    'on the left says:"You\'re Flying! How?", a floating '
                    'stick figure on the right responds "marimo!"'
                ),
                caption=(
                    'Original alt text: "<i>I wrote 20 short programs in '
                    "Python yesterday."
                    "<b> It was wonderful. </b>"
                    "Perl, <u>I'm leaving you.</u></i>\""
                    "<br/> The technologies may have changed, but the "
                    "sentiment remains. We agree Randall;<br /> Edited "
                    "from <u><a "
                    "    href='https://xkcd.com/353'>"
                    "        XKCD/353"
                    " </a></u> under CC-2.5;"
                ),
            )
        )
    else:
        mo.output.append(
            mo.Html(
                f"<iframe src='{url}' style='width:100%;height:500px'></iframe>",
            )
        )
    return True


def build_browser_fallback() -> type[webbrowser.BaseBrowser]:
    """
    Dynamically create the class since BaseBrowser does not exist in
    pyodide.
    """

    # Construct like this to limit stack frames.
    MarimoBrowser = type(
        "MarimoBrowser",
        (webbrowser.BaseBrowser,),
        {"open": staticmethod(browser_open_fallback)},
    )

    return MarimoBrowser
