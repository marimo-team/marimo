# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from inspect import cleandoc
from typing import Literal, Optional

import markdown  # type: ignore

from marimo._output.hypertext import Html
from marimo._output.md_extensions.external_links import ExternalLinksExtension
from marimo._output.rich_help import mddoc

extension_configs = {
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
    "footnotes": {
        "UNIQUE_IDS": True,
    },
}

MarkdownSize = Literal["sm", "base", "lg", "xl", "2xl"]


def _md(
    text: str,
    apply_markdown_class: bool = True,
    size: Optional[MarkdownSize] = None,
) -> Html:
    # cleandoc uniformly strips leading whitespace; useful for
    # indented multiline strings
    text = cleandoc(text)
    # markdown.markdown appends a newline, hence strip
    html_text = markdown.markdown(
        text,
        extensions=[
            # Syntax highlighting
            "codehilite",
            # Markdown tables
            "tables",
            # LaTeX
            "pymdownx.arithmatex",
            # Subscripts and strikethrough
            "pymdownx.tilde",
            # Better code blocks
            "pymdownx.superfences",
            # Table of contents
            # This adds ids to the HTML headers
            "toc",
            # Footnotes
            "footnotes",
            # Admonitions
            "admonition",
            # Links
            ExternalLinksExtension(),
        ],
        extension_configs=extension_configs,  # type: ignore[arg-type]
    ).strip()
    # replace <p> tags with <span> as HTML doesn't allow nested <div>s in <p>s
    html_text = html_text.replace("<p>", '<span class="paragraph">').replace(
        "</p>", "</span>"
    )

    if apply_markdown_class:
        classes = ["markdown", "prose", "dark:prose-invert"]
        if size is not None:
            classes.append(f"prose-{size}")
        return Html(f'<span class="{" ".join(classes)}">{html_text}</span>')
    else:
        return Html(html_text)


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
