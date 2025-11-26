import marimo

__generated_with = "0.17.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(markdown_sample, mo):
    mo.ui.table(
        {
            "heading": ["### Hello" * 8],
            "code_blocks": ["```python\n print('hi')\n```" * 3],
            "lists": ["- item 1\n* item 2\n1. item 3" * 3],
            "markdown_sample": [markdown_sample],
        }
    )
    return


@app.cell
def _():
    markdown_sample = """
       # Markdown showcase

        ## Features:
        - **Lists:**
          - Bullet points
          - Numbered lists

        - **Emphasis:** *italic*, **bold**, ***bold italic***
        - **Links:** [Visit OpenAI](https://www.openai.com)
        - **Images:**

        ![Picture](https://picsum.photos/200/300)

        - **Blockquotes:**

        > Markdown makes writing simple and beautiful!

        Enjoy exploring markdown's versatility!
    """
    return (markdown_sample,)


if __name__ == "__main__":
    app.run()
