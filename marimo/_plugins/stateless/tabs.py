# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._impl.tabs import tabs as tabs_impl
from marimo._utils.deprecated import deprecated


@mddoc
@deprecated("mo.tabs is deprecated. Use mo.ui.tabs instead")
def tabs(tabs: dict[str, object]) -> Html:
    """
    **Deprecated.**: Use `mo.ui.tabs` instead.

    Tabs of UI elements.

    **Examples.**

    ```python
    tab1 = mo.vstack([
        mo.ui.slider(1, 10),
        mo.ui.text(),
        mo.ui.date()
    ]);
    tab2 = mo.vstack([{
        "slider": mo.ui.slider(1, 10),
        "text": mo.ui.text(),
        "date": mo.ui.date()
    ]);
    tabs = mo.tabs({
        "Tab 1": tab1,
        "Tab 2": tab2
    })
    ```

    **Args.**

    - `tabs`: a dictionary of tab names to tab content; strings are interpreted
    as markdown

    **Returns.**

    - An `Html` object.
    """
    return tabs_impl(tabs)
