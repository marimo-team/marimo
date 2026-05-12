# Diagrams

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    mo.mermaid("graph TD\n  A[Christmas] -->|Get money| B(Go shopping)\n  B --> C{Let me think}\n  C -->|One| D[Laptop]\n  C -->|Two| E[iPhone]\n  C -->|Three| F[Car]")
    return
```

///

## Mermaid diagrams

Customize Mermaid styling with `theme` and `theme_variables`:

Theme only:

```python
mo.mermaid(
    diagram,
    theme="neutral",
)
```

```python
mo.mermaid(
    """
    graph TD
        A[Observed] --> B[Latent]
        B --> C[Posterior]
    """,
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

`theme` supports `"base"`, `"dark"`, `"default"`, `"forest"`,
`"neutral"`, and `"null"`.

By default, `mo.mermaid(diagram)` follows the app light/dark theme.

For supported `theme_variables` keys and defaults, see Mermaid's theming docs:

- [Theme configuration](https://mermaid.js.org/config/theming.html)
- [Theme variables reference](https://mermaid.js.org/config/theming.html#theme-variables)

Per Mermaid docs, custom `theme_variables` are reliably applied with
`theme="base"`.

If you pass `theme_variables` with `theme=None`, marimo automatically uses
`theme="base"`.

If you pass `theme_variables` with any explicit non-`base` theme,
`mo.mermaid(...)` raises a `ValueError`.

If custom colors are not appearing, make sure you are not combining
`theme_variables` with a non-`base` theme.

::: marimo.mermaid
