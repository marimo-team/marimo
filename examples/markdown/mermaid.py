# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.mermaid(
        """
    graph TD
        A[Enter Chart Definition] --> B(Preview)
        B --> C{decide}
        C --> D[Keep]
        C --> E[Edit Definition]
        E --> B
        D --> F[Save Image and Code]
        F --> B
    """
    ).center()
    return


@app.cell
def _(mo):
    graph = mo.ui.code_editor(
        value="""sequenceDiagram
        Alice->>John: Hello John, how are you?
        John-->>Alice: Great!
        Alice-)John: See you later!""",
        language="md",
        label="Mermaid editor",
    )
    graph
    return (graph,)


@app.cell
def _(graph, mo):
    mo.mermaid(graph.value).text
    return


@app.cell
def _(graph, mo):
    mo.md(f"""
    You can render mermaid directly inside `mo.md`. Using

    `mo.mermaid()`

    {mo.mermaid(graph.value).text}
    """)
    return


if __name__ == "__main__":
    app.run()
