import marimo

app = marimo.App(
    kwarg_that_doesnt_exist="title",
)

@app.cell(fake_kwarg=True)
def fake_kwarg():
    return
