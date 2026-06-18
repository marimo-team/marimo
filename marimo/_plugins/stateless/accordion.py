# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.formatting import as_html
from marimo._output.hypertext import ContainerHtml, Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.stateless.lazy import lazy as lazy_ui


class _AccordionHtml(ContainerHtml):
    """Html produced by `mo.accordion()`; keeps live references to its children."""

    def __init__(
        self,
        items: dict[str, object],
        multiple: bool = False,
        lazy: bool = False,
    ) -> None:
        self._multiple = multiple
        self._lazy = lazy

        self._tabs: list[Html]
        if self._lazy:
            self._tabs = [lazy_ui(tab) for tab in items.values()]
        else:
            self._tabs = [
                md(tab) if isinstance(tab, str) else as_html(tab)
                for tab in items.values()
            ]

        self._labels = [md(label) for label in items]

        super().__init__([*self._tabs, *self._labels])

    def _build_text(self) -> str:
        return build_stateless_plugin(
            component_name="marimo-accordion",
            args={
                "labels": [label.text for label in self._labels],
                "multiple": self._multiple,
            },
            slotted_html="".join(
                [f"<div>{tab.text}</div>" for tab in self._tabs]
            ),
        )


@mddoc
def accordion(
    items: dict[str, object], multiple: bool = False, lazy: bool = False
) -> Html:
    """Accordion of one or more items.

    Args:
        items: a dictionary of item names to item content; strings are
            interpreted as markdown
        multiple: whether to allow multiple items to be open simultaneously
        lazy: a boolean, whether to lazily load the accordion content.
            This is a convenience that wraps each accordion in a `mo.lazy`
            component.

    Returns:
        An `Html` object.

    Example:
        ```python3
        mo.accordion(
            {"Tip": "Use accordions to let users reveal and hide content."}
        )
        ```

        Accordion content can be lazily loaded:

        ```python3
        mo.accordion({"View total": expensive_item}, lazy=True)
        ```

        where `expensive_item` is the item to render, or a callable that
        returns the item to render.
    """

    return _AccordionHtml(items=items, multiple=multiple, lazy=lazy)
