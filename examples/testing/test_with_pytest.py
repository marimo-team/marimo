import marimo

__generated_with = "0.10.6"
app = marimo.App()


@app.cell
def _():
    def inc(x):
        return x + 1
    return inc


@app.cell
def test_answer(inc):
    assert inc(3) == 5, "This test fails"


@app.cell
def test_sanity(inc):
    assert inc(3) == 4, "This test passes"

if __name__ == "__main__":
	app.run()
