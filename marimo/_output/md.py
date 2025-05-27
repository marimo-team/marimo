# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from functools import cache
from importlib.util import find_spec
from inspect import cleandoc
from pathlib import Path
from typing import Any, Literal, Optional, Union
from urllib.request import urlopen

import markdown  # type: ignore
import markdown.preprocessors  # type: ignore
import pymdownx.emoji  # type: ignore

from marimo._output.hypertext import Html
from marimo._output.md_extensions.external_links import ExternalLinksExtension
from marimo._output.md_extensions.iconify import IconifyExtension
from marimo._output.rich_help import mddoc
from marimo._utils.url import is_url


class PyconDetectorExtension(markdown.Extension):
    """Markdown extension to detect Python console sessions and mark them as pycon."""

    def extendMarkdown(self, md: markdown.Markdown) -> None:
        """Add the preprocessor to the markdown instance."""
        processor = PyconDetectorPreprocessor(md)
        md.preprocessors.register(processor, "pycon_detector", 30)


class PyconDetectorPreprocessor(markdown.preprocessors.Preprocessor):
    """Preprocessor that detects Python console sessions in fenced code blocks.

    For example, the following code:

    ```
    >>> print("Hello, world!")
    ... print("Hello, world!")
    ```

    will be detected as a Python console session and marked as `pycon`.
    """

    def __init__(self, md: markdown.Markdown) -> None:
        super().__init__(md)
        # Pattern to match fenced code blocks
        self.fence_pattern = re.compile(
            r"^(\s*)```(\w*)\s*\n(.*?)^(\s*)```\s*$", re.MULTILINE | re.DOTALL
        )

    def run(self, lines: list[str]) -> list[str]:
        """Process the lines and detect pycon patterns."""
        text = "\n".join(lines)

        def replace_fence(match: re.Match[str]) -> str:
            indent = match.group(1)
            language = match.group(2) or ""
            code = match.group(3)

            # Only process if no language is specified
            if not language:
                if self._detect_pycon(code):
                    # Replace with pycon language
                    return f"{indent}```pycon\n{code}{indent}```"

            # Return original
            return match.group(0)

        modified_text = self.fence_pattern.sub(replace_fence, text)
        return modified_text.split("\n")

    def _detect_pycon(self, code: str) -> bool:
        """
        Detect if code contains Python console session patterns.

        Returns True if the code appears to be a Python console session
        (contains >>> or ... prompts).
        """
        lines = code.strip().split("\n")

        # Look for Python console prompts
        console_prompt_pattern = re.compile(r"^\s*>>>")
        continuation_prompt_pattern = re.compile(r"^\s*\.\.\.")

        # Count lines that look like console prompts
        prompt_lines = 0
        for line in lines:
            if console_prompt_pattern.match(
                line
            ) or continuation_prompt_pattern.match(line):
                prompt_lines += 1

        # If more than 30% of non-empty lines are prompts, likely a console session
        non_empty_lines = [line for line in lines if line.strip()]
        if len(non_empty_lines) == 0:
            return False

        return prompt_lines / len(non_empty_lines) > 0.3


@cache
def _get_extension_configs() -> dict[str, dict[str, Any]]:
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
        "pymdownx.highlight": {
            "use_pygments": True,
            # Try to guess the language of the code block
            "guess_lang": "block",
            # Show the language in the classname, helps with debugging and
            # customizing the styles
            "pygments_lang_class": True,
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

    return extension_configs


MarkdownSize = Literal["sm", "base", "lg", "xl", "2xl"]


def _has_module(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except Exception:
        return False


@cache
def _get_extensions() -> list[Union[str, markdown.Extension]]:
    return [
        # Syntax highlighting
        PyconDetectorExtension(),  # Python console detection (run before highlight)
        "pymdownx.highlight",
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
                    "pymdownx.blocks.admonition",
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
            extensions=_get_extensions(),
            extension_configs=_get_extension_configs(),
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

    ```python
    text_input = mo.ui.text()
    md(f"Enter some text: {text_input}")
    ```

    For other objects, like plots, use marimo's `as_html` method to embed
    them in markdown:

    ```python
    import matplotlib.pyplot as plt

    plt.plot([1, 2])
    axis = plt.gca()
    md(f"Here's a plot: {mo.as_html(axis)}")
    ```

    **LaTeX.**

    Enclose LaTeX in single '\$' signs for inline math, and double '\$\$' for
    display math or square brackets for display math. (Use raw strings,
    prefixed with an "r", to use single backslashes.) For example:

    ```python
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


    Args:
        text: a string of markdown

    Returns:
        An `Html` object.
    """
    return _md(text)


def latex(*, filename: Union[str, Path]) -> None:
    """Load LaTeX from a file or URL.

    ```python
    import marimo as mo

    mo.latex(filename="macros.tex")
    ```

    or

    ```python
    import marimo as mo

    mo.latex(filename="https://example.com/macros.tex")
    ```

    Args:
        filename: Path to a LaTeX file

    Returns:
        An `Html` object
    """

    if isinstance(filename, Path):
        text = filename.read_text()
    elif is_url(filename):
        with urlopen(filename) as response:
            text = response.read().decode("utf-8")
    elif (file := Path(filename)).exists():
        text = file.read_text()
    else:
        raise ValueError(f"Invalid filename: {filename}")

    from marimo._runtime import output

    # Append the LaTeX to the output, in case this
    # is not the last expression of the cell
    output.append(_md(f"$$\n{text.strip()}\n$$"))
    return
