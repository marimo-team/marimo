# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.core.web_component import build_stateless_plugin
from marimo._utils.dicts import remove_none_values


@mddoc
def mermaid(
    diagram: str,
    theme: str | None = None,
    theme_variables: dict[str, str] | None = None,
) -> Html:
    """Render a diagram with Mermaid.

    Mermaid is a tool for making diagrams such as flow charts and graphs. See
    the [Mermaid documentation](https://github.com/mermaid-js/mermaid#readme)
    for details.

    Args:
        diagram: a string containing a Mermaid diagram
        theme: optional Mermaid theme. See
            https://mermaid.js.org/config/theming.html#available-themes
            for available themes. If not provided, marimo picks
            a default based on app theme, unless `theme_variables` are
            provided.
        theme_variables: optional Mermaid `themeVariables` overrides.
            Mermaid defines supported keys and behavior; see
            https://mermaid.js.org/config/theming.html#theme-variables.
            If provided with `theme=None`, marimo automatically sets
            `theme="base"` so custom colors are applied.

    Returns:
        An `Html` object.

    Example:
        ```python
        diagram = '''
        graph LR
            A[Square Rect] -- Link text --> B((Circle))
            A --> C(Round Rect)
            B --> D{Rhombus}
            C --> D
        '''
        mo.mermaid(diagram)

        mo.mermaid(
            diagram,
            theme="base",
            theme_variables={
                "primaryColor": "#E8EEF5",
                "primaryTextColor": "#1F2937",
                "primaryBorderColor": "#64748B",
                "lineColor": "#475569",
                "tertiaryColor": "#F8FAFC",
            },
        )
        ```
    """
    if theme_variables is not None:
        if theme is None:
            theme = "base"
        elif theme != "base":
            raise ValueError(
                f"theme_variables require theme='base'. Got theme={theme!r}. "
                "See https://mermaid.js.org/config/theming.html"
            )

    return Html(
        build_stateless_plugin(
            component_name="marimo-mermaid",
            args=remove_none_values(
                {
                    "diagram": diagram,
                    "theme": theme,
                    "theme_variables": theme_variables,
                }
            ),
        )
    )
