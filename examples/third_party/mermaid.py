import marimo

__generated_with = "0.1.76"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
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
def __(mo):
    graph = mo.ui.code_editor(
        value="""sequenceDiagram
        Alice->>John: Hello John, how are you?
        John-->>Alice: Great!
        Alice-)John: See you later!""",
        language="mermaid",
        label="Mermaid editor",
    )
    graph
    return graph,


@app.cell
def __(graph, mo):
    mo.md(
        f"""
        You can render mermaid directly inside `mo.md`. Using

        `mo.mermaid()`

        {mo.mermaid(graph.value)}
        """
    )
    return


if __name__ == "__main__":
    app.run()
