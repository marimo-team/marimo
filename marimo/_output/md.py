# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import cache
from importlib.util import find_spec
from inspect import cleandoc
from typing import Any, Literal, Optional, Union

import markdown  # type: ignore
import pymdownx.emoji  # type: ignore

from marimo._output.hypertext import Html
from marimo._output.md_extensions.external_links import ExternalLinksExtension
from marimo._output.md_extensions.iconify import IconifyExtension
from marimo._output.rich_help import mddoc

extension_configs: dict[str, dict[str, Any]] = {
    "pymdownx.arithmatex": {
        # Use "generic" mode, no preview, since we don't use MathJax
        "preview": False,
        "generic": True,
        # The default "\\(" causes problems when passing
        # html-escaped `md` output back into `md`
        "tex_inline_wrap": ["||(", "||)"],
        "tex_block_wrap": ["||[", "||]"],
        # Wrap latex in a custom element
        "block_tag": "marimo-tex",
        "inline_tag": "marimo-tex",
    },
    "pymdownx.superfences": {
        "disable_indented_code_blocks": True,
        "css_class": "codehilite",
    },
    "pymdownx.emoji": {
        # This uses native emoji characters,
        # instead of loading from a CDN
        "emoji_generator": pymdownx.emoji.to_alt,
    },
    "footnotes": {
        "UNIQUE_IDS": True,
    },
}

MarkdownSize = Literal["sm", "base", "lg", "xl", "2xl"]


def _has_module(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except Exception:
        return False


@cache
def get_extensions() -> list[Union[str, markdown.Extension]]:
    return [
        # Syntax highlighting
        "codehilite",
        # Markdown tables
        "tables",
        # LaTeX
        "pymdownx.arithmatex",
        # Base64 is not enabled, since app users could potentially
        # use it to grab files they shouldn't have access to.
        # "pymdownx.b64",
        # Subscripts and strikethrough
        "pymdownx.tilde",
        # Better code blocks
        "pymdownx.superfences",
        # Task lists
        "pymdownx.tasklist",
        # Caption, Tabs, Details
        *(
            [
                module
                for module in [
                    "pymdownx.blocks.caption",
                    "pymdownx.blocks.tab",
                    "pymdownx.blocks.details",
                ]
                if _has_module(module)
            ]
        ),
        # Critic - color-coded markup
        "pymdownx.critic",
        # Emoji - :emoji:
        "pymdownx.emoji",
        # Keys - <kbd> support
        "pymdownx.keys",
        # Magic links - auto-link URLs
        "pymdownx.magiclink",
        # Table of contents
        # This adds ids to the HTML headers
        "toc",
        # Footnotes
        "footnotes",
        # Admonitions
        "admonition",
        # Sane lists, to include <ol start="n">
        "sane_lists",
        # Links
        ExternalLinksExtension(),
        # Iconify
        IconifyExtension(),
    ]


class _md(Html):
    def __init__(
        self,
        text: str,
        *,
        apply_markdown_class: bool = True,
        size: Optional[MarkdownSize] = None,
    ) -> None:
        # cleandoc uniformly strips leading whitespace; useful for
        # indented multiline strings
        text = cleandoc(text)
        self._markdown_text = text

        # Lazily add mo.notebook_dir() as the bas64 base path
        # if "pymdownx.b64" not in extension_configs:
        #     from marimo._runtime.runtime import notebook_dir

        #     extension_configs["pymdownx.b64"] = {
        #         "base_path": str(notebook_dir()),
        #     }

        # markdown.markdown appends a newline, hence strip
        html_text = markdown.markdown(
            text,
            extensions=get_extensions(),
            extension_configs=extension_configs,  # type: ignore[arg-type]
        ).strip()
        # replace <p> tags with <span> as HTML doesn't allow nested <div>s in <p>s
        html_text = html_text.replace(
            "<p>", '<span class="paragraph">'
        ).replace("</p>", "</span>")

        if apply_markdown_class:
            classes = ["markdown", "prose", "dark:prose-invert"]
            if size is not None:
                classes.append(f"prose-{size}")
            super().__init__(
                f'<span class="{" ".join(classes)}">{html_text}</span>'
            )
        else:
            super().__init__(html_text)

    def _repr_markdown_(self) -> str:
        return self._markdown_text


@mddoc
def md(text: str) -> Html:
    r"""Write markdown

    This function takes a string of markdown as input and returns an Html
    object. Output the object as the last expression of a cell to render
    the markdown in your app.

    **Interpolation.**

    You can interpolate Python values into your markdown strings, for example
    using f-strings. Html objects and UI elements can be directly interpolated.
    For example:

    ```python3
    text_input = mo.ui.text()
    md(f"Enter some text: {text_input}")
    ```

    For other objects, like plots, use marimo's `as_html` method to embed
    them in markdown:

    ```python3
    import matplotlib.pyplot as plt

    plt.plot([1, 2])
    axis = plt.gca()
    md(f"Here's a plot: {mo.as_html(axis)}")
    ```

    **LaTeX.**

    Enclose LaTeX in single '\$' signs for inline math, and double '\$\$' for
    display math or square brackets for display math. (Use raw strings,
    prefixed with an "r", to use single backslashes.) For example:

    ```python3
    mo.md(
        r'''
        The exponential function $f(x) = e^x$ can be represented as

        \[
            f(x) = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \ldots.
        \]
        '''
    )
    ```
    renders:

    The exponential function $f(x) = e^x$ can be represented as

    $$
    f(x) = 1 + x + \frac{x^2}{2!} + \frac{x^3}{3!} + \ldots.
    $$


    **Args**:

    - `text`: a string of markdown

    **Returns**:

    - An `Html` object.
    """
    return _md(text)
