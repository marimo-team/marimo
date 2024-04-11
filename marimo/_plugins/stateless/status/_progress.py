# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Iterable, Iterator, Optional, TypeVar

import marimo._runtime.output._output as output
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._utils.debounce import debounce

if TYPE_CHECKING:
    from collections.abc import Collection

S = TypeVar("S")
T = TypeVar("T")


def _remove_none_values(d: dict[S, T]) -> dict[S, T]:
    return {k: v for k, v in d.items() if v is not None}


class _Progress(Html):
    """A mutable class to represent a progress indicator in the UI."""

    def __init__(
        self,
        title: Optional[str],
        subtitle: Optional[str],
        total: Optional[int],
        show_rate: bool,
        show_eta: bool,
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.total = total
        self.current = 0
        self.closed = False
        # We show a loading spinner if total not known
        self.loading_spinner = total is None
        self.show_rate = show_rate
        self.show_eta = show_eta
        self.start_time = time.time()
        super().__init__(self._get_text())

    def __del__(self) -> None:
        super().__del__()

    def update_progress(
        self,
        increment: int = 1,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ) -> None:
        """Update the progress indicator.

        **Example.**

        ```python
        # Increment by 1
        progress.update()

        # Increment by 10 and update title and subtitle
        progress.update(10, title="Loading", subtitle="Still going...")
        ```

        **Args.**

        - increment: amount to increment by. Defaults to 1.
        - title: new title. Defaults to None.
        - subtitle: new subtitle. Defaults to None.
        """
        if self.closed:
            raise RuntimeError(
                "Progress indicators cannot be updated after exiting "
                "the context manager that created them. "
            )
        self.current += increment
        if title is not None:
            self.title = title
        if subtitle is not None:
            self.subtitle = subtitle

        self._text = self._get_text()
        self.debounced_flush()

    @debounce(0.15)
    def debounced_flush(self) -> None:
        """Flush the output to the UI"""
        output.flush()

    def clear(self) -> None:
        if self.closed:
            raise RuntimeError(
                "Progress indicators cannot be updated after exiting "
                "the context manager that created them. "
            )
        output.remove(self)

    def close(self) -> None:
        output.flush()  # Flush one last time before closing
        self.closed = True

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
                    "rate": self._get_rate(),
                    "eta": self._get_eta(),
                }
            ),
        )

    def _get_rate(self) -> Optional[float]:
        if self.show_rate:
            diff = time.time() - self.start_time
            if diff == 0:
                return None
            rate = self.current / diff
            return round(rate, 2)
        else:
            return None

    def _get_eta(self) -> Optional[float]:
        if self.show_eta and self.total is not None:
            rate = self._get_rate()
            if rate is not None and rate > 0:
                return round((self.total - self.current) / rate, 2)
            else:
                return None
        else:
            return None


class ProgressBar(_Progress):
    def __init__(
        self,
        title: str | None,
        subtitle: str | None,
        total: int,
        show_rate: bool,
        show_eta: bool,
    ) -> None:
        super().__init__(
            title=title,
            subtitle=subtitle,
            total=total,
            show_rate=show_rate,
            show_eta=show_eta,
        )

    def update(
        self,
        increment: int = 1,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        super().update_progress(
            increment=increment, title=title, subtitle=subtitle
        )


# TODO(akshayka): Add a `done()` method that turns the spinner into a checkmark
class Spinner(_Progress):
    """A spinner output representing a loading state"""

    def __init__(self, title: str | None, subtitle: str | None) -> None:
        super().__init__(
            title=title,
            subtitle=subtitle,
            total=None,
            show_rate=False,
            show_eta=False,
        )

    def update(
        self, title: str | None = None, subtitle: str | None = None
    ) -> None:
        """Update the title and subtitle of the spinner

        This method updates a spinner output in-place. Must be used
        in the cell the spinner was created.

        **Example.**

        ```python
        with mo.status.spinner("Hang tight!") as _spinner:
            ...
            _spinner.update(title="Almost done!")
        # Optionally, remove the spinner from the output
        # _spinner.clear()
        ```
        """
        super().update_progress(increment=1, title=title, subtitle=subtitle)


@mddoc
@contextlib.contextmanager
def spinner(
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    remove_on_exit: bool = True,
) -> Iterator[Spinner]:
    """Show a loading spinner

    Use `mo.status.spinner()` as a context manager to show a loading spinner.
    You can optionally pass a title and subtitle.

    **Example.**

    ```python
    with mo.status.spinner(subtitle="Loading data ...") as _spinner:
        data = expensive_function()
        _spinner.update(subtitle="Crunching numbers ...")
        ...

    mo.ui.table(data)
    ```

    **Args:**

    - `title`: optional title
    - `subtitle`: optional subtitle
    - `remove_on_exit`: if True, the spinner is removed from output on exit
    """
    spinner = Spinner(title=title, subtitle=subtitle)
    output.append(spinner)
    try:
        yield spinner
    finally:
        if remove_on_exit:
            spinner.clear()
        # TODO(akshayka): else consider transitioning to a done state
        spinner.close()


def progress_bar(
    collection: Collection[S | int],
    *,
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    completion_title: Optional[str] = None,
    completion_subtitle: Optional[str] = None,
    show_rate: bool = True,
    show_eta: bool = True,
) -> Iterable[S | int]:
    """Iterate over a collection and show a progress bar

    **Example.**

    ```python
    for i in mo.status.progress_bar(range(10)):
        ...
    ```

    You can optionally provide a title and subtitle to show
    during iteration, and a title/subtitle to show upon completion.

    For performance reasons, the progress bar is only updated in the UI
    every 150ms.

    **Args.**

    - `collection`: a collection to iterate over
    - `title`: optional title
    - `subtitle`: optional subtitle
    - `completion_title`: optional title to show during completion
    - `completion_subtitle`: optional subtitle to show during completion
    - `show_rate`: if True, show the rate of progress (items per second)
    - `show_eta`: if True, show the estimated time of completion

    **Returns.**

    An iterable object that wraps `collection`
    """
    if isinstance(collection, range):
        total = collection.stop - collection.start
        step = collection.step
    else:
        total = len(collection)
        step = 1
    progress = ProgressBar(
        title=title,
        subtitle=subtitle,
        total=total,
        show_rate=show_rate,
        show_eta=show_eta,
    )
    output.append(progress)
    for item in collection:
        yield item
        progress.update(increment=step)
    progress.update(
        increment=0, title=completion_title, subtitle=completion_subtitle
    )
    progress.close()
