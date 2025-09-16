import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.function
def inc(x):
    return x + 1


@app.cell
def test_answer():
    assert inc(3) == 5, "This test fails"
    return


@app.cell
def test_sanity():
    assert inc(3) == 4, "This test passes"
    return


if __name__ == "__main__":
    app.run()
