import weakref
from typing import TYPE_CHECKING, Any, Dict

import marimo._output.data.data as mo_data
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import UIElement

if TYPE_CHECKING:
    import anywidget

# Weak dictionary
# When the widget is deleted, the UIElement will be deleted as well
cache = weakref.WeakKeyDictionary["anywidget.AnyWidget", UIElement[Any, Any]]()


def from_anywidget(widget: "anywidget.AnyWidget") -> UIElement[Any, Any]:
    """Create a UIElement from an AnyWidget."""
    if widget not in cache:
        cache[widget] = _anywidget(widget)
    return cache[widget]


T = Dict[str, Any]


@mddoc
class _anywidget(UIElement[T, T]):
    """Create a UIElement from an AnyWidget."""

    def __init__(self, widget: "anywidget.AnyWidget"):
        self.widget = widget

        # Get all the traits of the widget
        args: T = widget.trait_values()
        ignored_traits = [
            "comm",
            "layout",
            "log",
            "tabbable",
            "tooltip",
            "keys",
        ]
        # Remove ignored traits
        for trait_name in ignored_traits:
            args.pop(trait_name, None)
        # Remove all private traits
        args = {k: v for k, v in args.items() if not k.startswith("_")}

        def on_change(change: T) -> None:
            for key, value in change.items():
                widget.set_trait(key, value)

        js: str = widget._esm if hasattr(widget, "_esm") else ""  # type: ignore
        css: str = widget._css if hasattr(widget, "_css") else ""  # type: ignore

        super().__init__(
            component_name="marimo-anywidget",
            initial_value=args,
            label="",
            args={
                "js-url": mo_data.js(js).url if js else "",  # type: ignore
                "css": css,
            },
            on_change=on_change,
        )

    def _convert_value(self, value: T) -> T:
        return value
