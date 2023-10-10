# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Collection
from typing import Iterable, Optional, TypeVar

import marimo._runtime.output._output as output
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin

S = TypeVar("S")
T = TypeVar("T")


def _remove_none_values(d: dict[S, T]) -> dict[S, T]:
    return {k: v for k, v in d.items() if v is not None}


class Progress(Html):
    """A mutable class to represent a progress indicator in the UI."""

    def __init__(
        self,
        title: Optional[str],
        subtitle: Optional[str],
        total: Optional[int],
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.total = total
        self.current = 0
        # We show a loading spinner if total not known
        self.loading_spinner = total is None
        self._text = self._get_text()

    def update(
        self,
        increment: int = 1,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ) -> None:
        """Update the progress indicator.

        **Example.**

        ```python
        # Increment by 1
        mo.loading.update()

        # Increment by 10 and update title and subtitle
        mo.loading.update(10, title="Loading", subtitle="Still going...")

        ```

        **Args**

        increment: amount to increment by. Defaults to 1.
        title: new title. Defaults to None.
        subtitle: new subtitle. Defaults to None.
        """
        self.current += increment
        if title is not None:
            self.title = title
        if subtitle is not None:
            self.subtitle = subtitle

        self._text = self._get_text()
        output.flush()

    def clear(self) -> None:
        self.title = None
        self.subtitle = None
        self.total = None
        self.current = 0
        self._text = ""
        output.flush()

    def _get_text(self) -> str:
        return build_stateless_plugin(
            component_name="marimo-progress",
            args=_remove_none_values(
                {
                    "title": self.title,
                    "subtitle": self.subtitle,
                    "total": self.total,
                    # 'progress' is True is we don't know the total,
                    # which shows a loading spinner
                    "progress": True if self.loading_spinner else self.current,
                }
            ),
        )


@mddoc
def spinner(
    title: Optional[str] = None, subtitle: Optional[str] = None
) -> None:
    """Show a loading spinner.

    Call `mo.loading.spinner()` to show a loading spinner.
    This is different than other UI elements in that it is immediately
    shown in the UI and does not disappear until:
    - It is replaced with `mo.output.replace()`
    - It is cleared with `mo.output.clear()`
    - A new element is returned in the final expression
        of a cell automatically replacing it.

    You can optionally pass a title.

    **Example.**

    ```python
    mo.loading.spinner(subtitle="Loading data from the server...")

    data = expensive_function()

    mo.ui.table(data)
    ```

    **Args:**

    - `title`: optional title
    - `subtitle`: optional subtitle
    """
    element = Html(
        build_stateless_plugin(
            component_name="marimo-progress",
            args=_remove_none_values(
                {
                    "title": title,
                    "subtitle": subtitle,
                    "progress": True,
                }
            ),
        )
    )
    output.append(element)


def progress_bar(
    collection: Collection[S | int],
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    completion_title: Optional[str] = None,
    completion_subtitle: Optional[str] = None,
) -> Iterable[S | int]:
    """Iterate over a collection and show a progress bar

    **Example.**

    ```python
    for i in mo.loading.progress_bar(range(10)):
        ...
    ```

    You can optionally provide a title and subtitle to show
    during iteration, and a title/subtitle to show upon completion.

    **Args.**

    - `collection`: a collection to iterate over
    - `title`: optional title
    - `subtitle`: optional subtitle
    - `completion_title`: optional title to show during completion
    - `completion_subtitle`: optional subtitle to show during completion

    **Returns.**

    An iterable object that wraps `collection`
    """
    if isinstance(collection, range):
        total = collection.stop - collection.start
        step = collection.step
    else:
        total = len(collection)
        step = 1
    progress = Progress(title=title, subtitle=subtitle, total=total)
    output.append(progress)
    for item in collection:
        yield item
        progress.update(increment=step)
    progress.update(title=completion_title, subtitle=completion_subtitle)
