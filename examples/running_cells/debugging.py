import marimo

__generated_with = "0.12.9"
app = marimo.App()


@app.cell
def foo():
    def foo(x):
        breakpoint()
        return 1 / x
    return (foo,)


@app.cell
def _(foo):
    foo(1)
    return


if __name__ == "__main__":
    app.run()
