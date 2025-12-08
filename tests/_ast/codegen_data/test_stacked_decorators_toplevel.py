import marimo

__generated_with = "0.18.2"
app = marimo.App()

with app.setup:
    import marimo as mo
    wrap = lambda x: x


@app.function
# comment after app.function
@mo.cache
# comment after cache
def cached_func():
    return 42


@app.cell
def normal_cell():
    a = 1
    return (a,)


@app.class_definition
@wrap
class Foo: ...


@app.cell(hide_code=True)
def _():
    with mo.cache("example"):
        print("Hello")
    return


if __name__ == "__main__":
    app.run()
