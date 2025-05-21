# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Optional,
    TypeVar,
)

import marimo._runtime.output._output as output
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.ops import Alert
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._utils.debounce import debounce

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

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

    def update_progress(
        self,
        increment: int = 1,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
    ) -> None:
        """Update the progress indicator.

        Examples:
            Increment by 1:
            ```python
            # Increment by 1
            progress.update()
            ```

            Increment by 10 and update title and subtitle:
            ```python
            # Increment by 10 and update title and subtitle
            progress.update(10, title="Loading", subtitle="Still going...")
            ```

        Args:
            increment (int, optional): Amount to increment by. Defaults to 1.
            title (str, optional): New title. Defaults to None.
            subtitle (str, optional): New subtitle. Defaults to None.
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
        """Flush the output to the UI."""
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

    def _calculate_rate(self) -> Optional[float]:
        diff = time.time() - self.start_time
        if diff == 0:
            return None
        rate = self.current / diff
        return round(rate, 2)

    def _get_rate(self) -> Optional[float]:
        if self.show_rate:
            return self._calculate_rate()
        else:
            return None

    def _get_eta(self) -> Optional[float]:
        if self.show_eta and self.total is not None:
            rate = self._calculate_rate()
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

    def __init__(
        self,
        title: str | None,
        subtitle: str | None,
    ) -> None:
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
        """Update the title and subtitle of the spinner.

        This method updates a spinner output in-place. Must be used
        in the cell the spinner was created.

        Examples:
            ```python
            with mo.status.spinner("Hang tight!") as _spinner:
                ...
                _spinner.update(title="Almost done!")
            # Optionally, remove the spinner from the output
            # _spinner.clear()
            ```

        Args:
            title (str, optional): New title. Defaults to None.
            subtitle (str, optional): New subtitle. Defaults to None.
        """
        super().update_progress(increment=1, title=title, subtitle=subtitle)


@mddoc
class spinner:
    """Show a loading spinner.

    Use `mo.status.spinner()` as a context manager to show a loading spinner.
    You can optionally pass a title and subtitle.

    Examples:
        ```python
        with mo.status.spinner(subtitle="Loading data ...") as _spinner:
            data = expensive_function()
            _spinner.update(subtitle="Crunching numbers ...")
            ...

        mo.ui.table(data)
        ```

        You can also show the spinner without a context manager:
        ```python
        mo.status.spinner(title="Loading ...") if condition else mo.md("Done!")
        ```

    Args:
        title (str, optional): Optional title.
        subtitle (str, optional): Optional subtitle.
        remove_on_exit (bool, optional): If True, the spinner is removed from output on exit.
            Defaults to True.
    """

    def __init__(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        remove_on_exit: bool = True,
    ):
        self.title = title
        self.subtitle = subtitle
        self.remove_on_exit = remove_on_exit
        self.spinner = Spinner(title=self.title, subtitle=self.subtitle)

    def __enter__(self) -> Spinner:
        output.append(self.spinner)
        return self.spinner

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        if self.remove_on_exit:
            self.spinner.clear()
        # TODO(akshayka): else consider transitioning to a done state
        self.spinner.close()

    def _mime_(self) -> tuple[KnownMimeType, str]:
        return self.spinner._mime_()


class progress_bar:
    """Iterate over a collection and show a progress bar.

    Examples:
        ```python
        for i in mo.status.progress_bar(range(10)):
            ...
        ```

        You can optionally provide a title and subtitle to show
        during iteration, and a title/subtitle to show upon completion:
        ```python
        with mo.status.progress_bar(total=10) as bar:
            for i in range(10):
                ...
                bar.update()
        ```

        The `update` method accepts the optional keyword
        arguments `increment` (defaults to `1`), `title`,
        and `subtitle`.

        For performance reasons, the progress bar is only updated in the UI
        every 150ms.

    Args:
        collection (Collection[Union[S, int]], optional): Optional collection to iterate over.
        title (str, optional): Optional title.
        subtitle (str, optional): Optional subtitle.
        completion_title (str, optional): Optional title to show during completion.
        completion_subtitle (str, optional): Optional subtitle to show during completion.
        total (int, optional): Optional total number of items to iterate over.
        show_rate (bool, optional): If True, show the rate of progress (items per second).
        show_eta (bool, optional): If True, show the estimated time of completion.
        remove_on_exit (bool, optional): If True, remove the progress bar from output on exit.
        disabled (bool, optional): If True, disable the progress bar.
    """

    def __init__(
        self,
        collection: Optional[Collection[S | int]] = None,
        *,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        completion_title: Optional[str] = None,
        completion_subtitle: Optional[str] = None,
        total: Optional[int] = None,
        show_rate: bool = True,
        show_eta: bool = True,
        remove_on_exit: bool = False,
        disabled: bool = False,
    ):
        self.completion_title = completion_title
        self.completion_subtitle = completion_subtitle
        self.remove_on_exit = remove_on_exit
        self.disabled = disabled

        if collection is not None:
            self.collection = collection

            try:
                total = total or len(collection)
                self.step = (
                    collection.step if isinstance(collection, range) else 1
                )
            except TypeError:  # if collection is a generator
                raise TypeError(
                    "fail to determine length of collection, use `total`"
                    + "to specify"
                ) from None

        elif total is None:
            raise ValueError(
                "`total` is required when using as a context manager"
            )

        self.progress = ProgressBar(
            title=title,
            subtitle=subtitle,
            total=total,
            show_rate=show_rate,
            show_eta=show_eta,
        )
        if not disabled:
            output.append(self.progress)

    def __iter__(self) -> Iterable[S | int]:
        for item in self.collection:
            yield item  # type: ignore[misc]
            if not self.disabled:
                self.progress.update(increment=self.step)
        self._finish()

    def __enter__(self) -> ProgressBar:
        return self.progress

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self._finish()

    def _finish(self) -> None:
        self.progress.update(
            increment=0,
            title=self.completion_title,
            subtitle=self.completion_subtitle,
        )
        if self.remove_on_exit:
            self.progress.clear()
        self.progress.close()


@mddoc
def toast(
    title: str,
    description: str = "",
    kind: Optional[Literal["danger"]] = None,
) -> None:
    """Show a toast notification.

    Use `mo.status.toast()` to display a brief notification.

    Examples:
        ```python
        mo.status.toast(
            "Operation completed",
            "Your task has finished successfully",
        )
        ```

    Args:
        title (str): The main message of the toast.
        description (str, optional): Optional additional details (can include HTML).
            Defaults to "".
        kind (Literal["danger"], optional): Optional kind, use "danger" for error toasts.
            Defaults to None.
    """
    Alert(title=title, description=description, variant=kind).broadcast()
