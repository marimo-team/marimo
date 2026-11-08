# Copyright 2026 Marimo. All rights reserved.
"""Static-export pre-rendering of `mo.ui.tabs` variants.

A static HTML export has no kernel, so cells that depend on the value of a
`mo.ui.tabs` element cannot re-run when the reader switches tabs. To keep
such notebooks useful, the HTML exporter runs the notebook once per tab
value, keeps the outputs that differ from the default run, and embeds every
variant in the exported page; a small script (see `_TAB_VARIANT_SCRIPT` in
`marimo/_templates.py`) then shows the variant matching the selected tab.
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import TYPE_CHECKING

from marimo import _loggers

if TYPE_CHECKING:
    from marimo._session.state.session_view import SessionView
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

# Output mimetypes whose data is a string of HTML and can therefore carry
# the variant wrapper markup.
_HTML_MIMETYPES = ("text/html", "text/markdown")

# Upper bound on the number of additional notebook runs used to pre-render
# tab variants. Every extra `mo.ui.tabs` element multiplies the number of
# runs, so without a cap exports could take unexpectedly long.
MAX_TAB_VARIANT_RUNS = 8


@dataclass(frozen=True)
class TabsElement:
    """A `mo.ui.tabs` element found in a session's outputs."""

    object_id: str
    cell_id: CellId_t
    num_tabs: int
    initial_index: int


class _TabsFinder(HTMLParser):
    """Collect `marimo-tabs` elements and their UI element object ids."""

    def __init__(self) -> None:
        super().__init__()
        self._ui_stack: list[str | None] = []
        # Stack of in-progress tabs: (object_id, tab count, initial value).
        self._tabs_stack: list[tuple[str | None, int, str | None]] = []
        self.found: list[tuple[str | None, int, str | None]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attrs_dict = dict(attrs)
        if tag == "marimo-ui-element":
            self._ui_stack.append(attrs_dict.get("object-id"))
        elif tag == "marimo-tabs":
            object_id = self._ui_stack[-1] if self._ui_stack else None
            self._tabs_stack.append(
                (object_id, 0, attrs_dict.get("data-initial-value"))
            )
        elif (
            tag == "div"
            and self._tabs_stack
            and attrs_dict.get("data-kind") == "tab"
        ):
            object_id, count, initial = self._tabs_stack.pop()
            self._tabs_stack.append((object_id, count + 1, initial))

    def handle_endtag(self, tag: str) -> None:
        if tag == "marimo-tabs" and self._tabs_stack:
            object_id, count, initial = self._tabs_stack.pop()
            self.found.append((object_id, count, initial))
        elif tag == "marimo-ui-element" and self._ui_stack:
            self._ui_stack.pop()


def _parse_initial_index(raw: str | None) -> int:
    # data-initial-value is a JSON-encoded string of the tab index.
    try:
        return int(json.loads(raw or '"0"'))
    except (ValueError, TypeError):
        return 0


def find_tabs_elements(
    session_view: SessionView, cell_ids: list[CellId_t]
) -> list[TabsElement]:
    """Find `mo.ui.tabs` elements in a session's outputs.

    Only elements with deterministic object ids (`<cell_id>-<n>`) are
    returned, since only those can be assigned a value before a notebook
    run (see `UIElement`'s stable IDs).
    """
    cell_id_set = set(cell_ids)
    elements: list[TabsElement] = []
    for cell_id, notification in session_view.cell_notifications.items():
        output = notification.output
        if output is None or output.mimetype not in _HTML_MIMETYPES:
            continue
        data = output.data
        if not isinstance(data, str) or "<marimo-tabs" not in data:
            continue
        finder = _TabsFinder()
        try:
            finder.feed(data)
        except Exception:
            LOGGER.warning(
                "Failed to parse outputs of cell %s for tabs elements.",
                cell_id,
                exc_info=True,
            )
            continue
        for object_id, num_tabs, raw_initial in finder.found:
            if object_id is None or num_tabs == 0:
                continue
            prefix, _, counter = object_id.rpartition("-")
            if (
                prefix not in cell_id_set
                or not counter.isdigit()
                or "-" in prefix
            ):
                # Not a deterministic `<cell_id>-<n>` id; the element's
                # value cannot be preset across runs.
                continue
            elements.append(
                TabsElement(
                    object_id=object_id,
                    cell_id=cell_id,
                    num_tabs=num_tabs,
                    initial_index=_parse_initial_index(raw_initial),
                )
            )
    return elements


def compute_tab_variant_combos(
    elements: list[TabsElement],
) -> list[dict[str, str]] | None:
    """Compute the tab-value combinations that need extra runs.

    Returns None when there is nothing to pre-render (no elements, or the
    number of runs would exceed `MAX_TAB_VARIANT_RUNS`).
    """
    if not elements:
        return None
    default = {
        element.object_id: str(element.initial_index) for element in elements
    }
    # Full combinations (every element assigned a value); the toggle
    # script matches on these keys, so defaults are included explicitly.
    combos = [
        {
            element.object_id: value
            for element, value in zip(elements, values, strict=True)
        }
        for values in itertools.product(
            *[
                [str(index) for index in range(element.num_tabs)]
                for element in elements
            ]
        )
        if {
            element.object_id: value
            for element, value in zip(elements, values, strict=True)
        }
        != default
    ]
    if not combos:
        return None
    if len(combos) > MAX_TAB_VARIANT_RUNS:
        LOGGER.warning(
            "Skipping tab variant pre-rendering: %d runs would be needed "
            "(max %d).",
            len(combos),
            MAX_TAB_VARIANT_RUNS,
        )
        return None
    return combos


def combo_key(combo: dict[str, str]) -> str:
    """Stable string key for a tab-value combination."""
    return ";".join(f"{k}:{combo[k]}" for k in sorted(combo))


def _normalize_for_diff(html: str) -> str:
    # `random-id` changes on every construction by design; it must not
    # make two otherwise identical outputs look different.
    return re.sub(r'random-id="[^"]*"', 'random-id=""', html)


def diff_tab_variants(
    default_view: SessionView,
    variant_views: dict[str, SessionView],
    default_combo: dict[str, str],
) -> dict[CellId_t, dict[str, dict[str, str]]]:
    """Find cells whose outputs differ across tab values.

    Returns a mapping of cell id to a mapping of combo key to the
    `{mimetype: html}` outputs that should be embedded for that combo.
    Cells containing a `marimo-tabs` element are excluded: the element
    itself already toggles, and duplicating it per variant would render
    several copies of the tab bar.
    """
    default_key = combo_key(default_combo)
    affected: dict[CellId_t, dict[str, dict[str, str]]] = {}
    for cell_id, notification in default_view.cell_notifications.items():
        output = notification.output
        if output is None or output.mimetype not in _HTML_MIMETYPES:
            continue
        data = output.data
        if not isinstance(data, str) or "<marimo-tabs" in data:
            continue
        default_html = _normalize_for_diff(data)
        combos: dict[str, dict[str, str]] = {
            default_key: {output.mimetype: data}
        }
        for key, view in variant_views.items():
            variant_notification = view.cell_notifications.get(cell_id)
            variant_output = (
                variant_notification.output
                if variant_notification is not None
                else None
            )
            if variant_output is None:
                continue
            variant_data = variant_output.data
            if variant_output.mimetype != output.mimetype or not isinstance(
                variant_data, str
            ):
                continue
            if _normalize_for_diff(variant_data) != default_html:
                combos[key] = {output.mimetype: variant_data}
        if len(combos) > 1:
            affected[cell_id] = combos
    return affected


def apply_tab_variants_to_view(
    session_view: SessionView,
    affected: dict[CellId_t, dict[str, dict[str, str]]],
    default_combo: str,
) -> bool:
    """Wrap affected cells' outputs so variants toggle with the tabs.

    Mutates `session_view` in place. Returns True when any cell was wrapped.
    """
    wrapped_any = False
    for cell_id, combos in affected.items():
        notification = session_view.cell_notifications.get(cell_id)
        if notification is None or notification.output is None:
            continue
        output = notification.output
        if output.mimetype not in _HTML_MIMETYPES:
            continue
        mime_variants = combos.get(default_combo)
        if mime_variants is None or output.mimetype not in mime_variants:
            continue
        parts: list[str] = []
        for key in sorted(combos):
            html = combos[key][output.mimetype]
            hidden = "" if key == default_combo else " hidden"
            parts.append(f'<div data-tab-combo="{key}"{hidden}>{html}</div>')
        output.data = f"<div data-marimo-tab-variants>{''.join(parts)}</div>"
        wrapped_any = True
    return wrapped_any


def describe_variants(elements: list[TabsElement]) -> str:
    return ", ".join(f"{e.object_id} ({e.num_tabs} tabs)" for e in elements)
