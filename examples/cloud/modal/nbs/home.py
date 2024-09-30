import marimo

__generated_with = "0.8.4"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("""# Hello, from inside Modal!""")
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
