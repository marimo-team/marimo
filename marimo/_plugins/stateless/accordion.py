# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._output.formatting import as_html
from marimo._output.hypertext import ContainerHtml, Html
from marimo._output.md import md
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._plugins.stateless.lazy import lazy as lazy_ui

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


@mddoc
class accordion(ContainerHtml):
    """An `Html` object representing an accordion of one or more items.

    Args:
        items: a mapping of item names to item content; strings are
            interpreted as markdown
        multiple: whether to allow multiple items to be open simultaneously
        lazy: a boolean, whether to lazily load the accordion content.
            This is a convenience that wraps each accordion in a `mo.lazy`
            component.
        expanded: the items to expand initially. `True` expands the first
            item, or all items with `multiple=True`. A sequence of item keys
            expands those items. More than one distinct key requires
            `multiple=True`. Keys must match the original keys in `items`.
            Users can still open and close items.

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

        Expand all items initially:

        ```python3
        mo.accordion(
            {"Summary": "Overview", "Details": "More information"},
            multiple=True,
            expanded=True,
        )
        ```

        Expand a specific item initially:

        ```python3
        mo.accordion(
            {"Summary": "Overview", "Details": "More information"},
            expanded=["Details"],
        )
        ```
    """

    def __init__(
        self,
        items: Mapping[str, object],
        multiple: bool = False,
        lazy: bool = False,
        *,
        expanded: bool | Sequence[str] = False,
    ) -> None:
        self._multiple = multiple
        self._lazy = lazy

        if isinstance(expanded, bool):
            count = len(items) if multiple else min(1, len(items))
            self._expanded = [str(i) for i in range(count)] if expanded else []
        else:
            if isinstance(expanded, str):
                raise TypeError(
                    "expanded must be a bool or a sequence of item keys. "
                    'Use ["key"] instead of "key".'
                )
            indices = {key: str(i) for i, key in enumerate(items)}
            keys = dict.fromkeys(expanded)
            for key in keys:
                if key not in indices:
                    raise ValueError(f"Unknown expanded item key: {key!r}")
            if not multiple and len(keys) > 1:
                raise ValueError(
                    "Expanding more than one item requires multiple=True."
                )
            self._expanded = [indices[key] for key in keys]

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
                "expanded": self._expanded,
            },
            slotted_html="".join(
                [f"<div>{tab.text}</div>" for tab in self._tabs]
            ),
        )
