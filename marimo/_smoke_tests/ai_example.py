import marimo

__generated_with = "0.8.19"
app = marimo.App()


@app.cell
def __():
    import marimo as mo

    return (mo,)


@app.cell
def __(mo):
    a = mo.ai.chat(
        model=mo.ai.models.openai("gpt-4-turbo"),
    )
    a
    return (a,)


@app.cell
def __(a):
    a.value
    return


if __name__ == "__main__":
    app.run()
