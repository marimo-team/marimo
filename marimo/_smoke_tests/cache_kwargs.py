import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    kw = {"some_kw_arg": 30}
    some_arg1 = 1
    return (kw,)


@app.cell
def _():
    1
    return


@app.cell
def _(mo):
    class C:
        @mo.persistent_cache
        def my_cached_func(self, *args, **kwargs):
            return args[0] + kwargs["some_kw_arg"]


    my_cached_func = C().my_cached_func
    return (my_cached_func,)


@app.cell
def _(kw, my_cached_func):
    # Expect (persistent) caching correctly capture changes in kw, but it doesn't.
    # breakpoint()
    my_cached_func(**kw)
    return


@app.cell
def _(my_cached_func):
    my_cached_func.hits
    return


@app.cell
def _():


    return


if __name__ == "__main__":
    app.run()
