import marimo

__generated_with = "0.2.8"
app = marimo.App()


@app.cell
def f():
    x = 0
    return (x,)


@app.cell
def g(x):
    y = x + 1
    return (y,)


@app.cell
def h(y):
    z = y + 1
    z
    return (z,)


@app.cell
def unhashable_defined():
    unhashable = {0, 1, 2}
    unhashable
    return (unhashable,)


@app.cell
def unhashable_override_required(unhashable):
    assert unhashable == {0, 1}
    unhashable
    return


@app.cell
def multiple():
    A = 0
    B = 1
    (A, B)
    return (A, B)

if __name__ == "__main__":
    app.run()
