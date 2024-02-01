import marimo

__generated_with = "0.1.88"
app = marimo.App()


@app.cell
def __():
    import marimo as mo

    form = mo.ui.text().form()
    form
    return form, mo


@app.cell
def __(form, mo):
    mo.stop(not form.value, "None")
    print(form.value[::-1])
    form.value
    return


if __name__ == "__main__":
    app.run()
