import marimo

__generated_with = "0.21.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import random
    import polars as pl

    return mo, pl, random


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Copy Rich Content from Tables

    Test copying and filtering cells with rich HTML content.

    - **Right-click → Copy cell** should preserve hyperlinks (text/html clipboard)
    - **Ctrl+C multi-cell** should produce an HTML table alongside tab-separated text
    - **Right-click → Filter by this value** should use the raw value, not the HTML
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Table with `format_mapping` (hyperlinks)
    """)
    return


@app.cell
def _(mo):
    data = {
        "id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
        "score": [95, 87, 72, 91, 88],
        "website": [
            "https://example.com/alice",
            "https://example.com/bob",
            "https://example.com/charlie",
            "https://example.com/diana",
            "https://example.com/eve",
        ],
    }

    mo.ui.table(
        data,
        format_mapping={
            "name": lambda name: mo.md(f"**{name}**"),
            "score": lambda score: mo.md(
                f'<span style="color: {"green" if score >= 90 else "orange"}">{score}</span>'
            ),
            "website": lambda url: mo.md(f"[Visit site]({url})"),
        },
        label="Hyperlinks via format_mapping",
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Table with mixed content (UI elements + plain values)
    """)
    return


@app.cell
def _(mo):
    mo.ui.table(
        {
            "label": ["Enable feature", "Dark mode", "Notifications"],
            "toggle": [
                mo.ui.checkbox(label="On"),
                mo.ui.checkbox(label="Off"),
                mo.ui.checkbox(label="On", value=True),
            ],
            "priority": [1, 2, 3],
        },
        label="Mixed: UI elements + plain values",
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Table with `mo.Html()` (text/html mime)
    """)
    return


@app.cell
def _(mo):
    mo.ui.table(
        {
            "link": [
                mo.Html('<a href="https://marimo.io">marimo</a>'),
                mo.Html('<a href="https://github.com">GitHub</a>'),
                mo.Html('<a href="https://python.org">Python</a>'),
            ],
            "badge": [
                mo.Html(
                    '<span style="background: green; color: white; padding: 2px 6px; border-radius: 4px">Active</span>'
                ),
                mo.Html(
                    '<span style="background: red; color: white; padding: 2px 6px; border-radius: 4px">Inactive</span>'
                ),
                mo.Html(
                    '<span style="background: orange; color: white; padding: 2px 6px; border-radius: 4px">Pending</span>'
                ),
            ],
            "plain": ["alpha", "beta", "gamma"],
        },
        label="Raw HTML via mo.Html()",
    )
    return


@app.cell
def _(mo):
    mo.md("""
    ## Table with inline markdown (no format_mapping)
    """)
    return


@app.cell
def _(mo):
    mo.ui.table(
        {
            "description": [
                mo.md("Contains **bold** text"),
                mo.md("Contains `inline code`"),
                mo.md("[A hyperlink](https://marimo.io)"),
            ],
            "plain": ["alpha", "beta", "gamma"],
        },
        label="Inline markdown as values (text/markdown mime)",
    )
    return


@app.cell
def _(mo, pl, random):
    def url(k):
        return mo.md(f"[{k}](https://www.google.com/search?q={k})")


    _random_numbers = [random.randint(1, 100) for _ in range(10)]
    df = pl.DataFrame({"filter_by_this": _random_numbers})

    mo.ui.table(df, format_mapping={"filter_by_this": url})
    return


if __name__ == "__main__":
    app.run()
