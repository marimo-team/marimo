import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")


@app.class_definition
# This should be reusable
class One:
    A: int = 1

    def run(a: A = 1) -> int:
        return a


@app.class_definition
# This should be a pure-class
class Two:
    A: int = 1

    def run(a: int = 1) -> int:
        return a


@app.cell
def _():
    C = int
    return (C,)


@app.cell
def _():
    value = 1
    return (value,)


@app.cell
def _(C):
    # This should NOT be reusable (depends on C)
    class Three:
        A: int = 1
        B: int = 1

        def run(a: C = 1) -> int:
            return a
    return


@app.cell
def _(C):
    # This should NOT be reusable (depends on C)
    class Four:
        A: int = 1
        B: C = 1

        def run(a: B = 1) -> int:
            return a
    return


@app.cell
def _(value):
    # This should NOT be reusable (depends on value)
    class Five:
        A: int = 1

        def run(a: A = value) -> int:
            return a
    return


if __name__ == "__main__":
    app.run()
