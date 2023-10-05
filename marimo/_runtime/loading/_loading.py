# Copyright 2023 Marimo. All rights reserved.
import sys

from typing import Optional

from marimo._output.rich_help import mddoc
import marimo._runtime.output._output as output
from marimo._runtime.context import get_context
from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import build_stateless_plugin

class Progress(Html):
    def __init__(self,
        title: Optional[str],
        subtitle: Optional[str],
        total: Optional[int],
        ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.total = total
        self.current = 0
        self.loading_spinner = total is None
        self._text = self._get_text()

    def update(self,
               increment: int = 1,
               title: Optional[str] = None,
               subtitle: Optional[str] = None,
        ) -> None:
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
            args={
                "title": self.title,
                "subtitle": self.subtitle,
                "total": self.total,
                "progress": True if self.loading_spinner else self.current,
            },
        )



@mddoc
def start(
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    total: Optional[int] = None,
) -> Progress:
    """Create a new progress indicator.

    Call `mo.loading.progress()` to create a progress indicator.

    You can optionally pass a title, subtitle, and total number of steps to completion.

    **Example.**

    ```python
    progress = mo.loading.progress(
        title="Loading",
        subtitle="This may take a while...",
        total=100
    )
    ```

    **Args:**

    - `title`: optional title
    - `subtitle`: optional subtitle
    - `total`: optional total number of steps to completion
    """
    progress = Progress(title=title, subtitle=subtitle, total=total)
    output.append(progress)
    return progress

