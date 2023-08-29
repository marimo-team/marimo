# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, final

from marimo._output.mime import MIME
from marimo._output.rich_help import mddoc

if TYPE_CHECKING:
    from marimo._plugins.core.web_component import JSONType
    from marimo._plugins.ui._core.ui_element import UIElement
    from marimo._plugins.ui._impl.batch import batch as batch_plugin


@mddoc
class Html(MIME):
    """A wrapper around HTML text that can be used as an output.

    Output an `Html` object as the last expression of a cell to render it in
    your app.

    Use f-strings to embed Html objects as text into other HTML or markdown
    strings. For example:

    ```python3
    hello_world = Html('<h2>Hello, World</h2>')
    Html(
        f'''
        <h1>Hello, Universe!</h1>
        {hello_world}
        '''
    )
    ```

    **Attributes.**

    - `text`: a string of HTML

    **Initialization Args.**

    - `text`: a string of HTML

    **Methods.**

    - `batch`: convert this HTML element into a batched UI element
    - `callout`: wrap this element in a callout
    - `center`: center this element in the output area
    - `right`: right-justify this element in the output area
    """

    _text: str

    def __init__(self, text: str) -> None:
        self._text = text

    @property
    def text(self) -> str:
        """A string of HTML representing this element."""
        return self._text

    @final
    def _mime_(self) -> tuple[str, str]:
        return ("text/html", self.text)

    def __format__(self, spec: str) -> str:
        """Format `self` as HTML text"""
        del spec
        return "".join([line.strip() for line in self.text.split("\n")])

    @mddoc
    def batch(self, **elements: UIElement[JSONType, object]) -> batch_plugin:
        """Convert an HTML object with templated text into a UI element.

        This method lets you create custom UI elements that are represented
        by arbitrary HTML.

        **Example.**

        ```python3
        user_info = mo.md(
            '''
            - What's your name?: {name}
            - When were you born?: {birthday}
            '''
        ).batch(name=mo.ui.text(), birthday=mo.ui.date())
        ```

        In this example, `user_info` is a UI Element whose output is markdown
        and whose value is a dict with keys `'name'` and '`birthday`'
        (and values equal to the values of their corresponding elements).

        **Args.**

        - elements: the UI elements to interpolate into the HTML template.
        """
        from marimo._plugins.ui._impl.batch import batch as batch_plugin

        return batch_plugin(html=self, elements=elements)

    @mddoc
    def center(self) -> Html:
        """Center an item.

        **Example.**

        ```python3
        mo.md("# Hello, world").center()
        ```

        **Returns.**

        An `Html` object.
        """
        from marimo._plugins.stateless import flex

        return flex.hstack([self], justify="center")

    @mddoc
    def right(self) -> Html:
        """Right-justify.

        **Example.**

        ```python3
        mo.md("# Hello, world").right()
        ```

        **Returns.**

        An `Html` object.
        """
        from marimo._plugins.stateless import flex

        return flex.hstack([self], justify="end")

    @mddoc
    def left(self) -> Html:
        """Left-justify.

        **Example.**

        ```python3
        mo.md("# Hello, world").left()
        ```

        **Returns.**

        An `Html` object.
        """
        from marimo._plugins.stateless import flex

        return flex.hstack([self], justify="start")

    @mddoc
    def callout(
        self,
        kind: Literal[
            "neutral", "danger", "warn", "success", "info"
        ] = "neutral",
    ) -> Html:
        """Create a callout containing this HTML element.

        A callout wraps your HTML element in a raised box, emphasizing its
        importance. You can style the callout for different situations with the
        `kind` argument.

        **Examples.**

        ```python3
        mo.md("Hooray, you did it!").callout(kind="success")
        ```

        ```python3
        mo.md("It's dangerous to go alone!").callout(kind="warn")
        ```
        """

        from marimo._plugins.stateless.callout_output import (
            callout as _callout,
        )

        return _callout(self, kind=kind)


def _js(text: str) -> Html:
    # TODO: interpolation of Python values to javascript
    return Html("<script>" + text + "</script>")
