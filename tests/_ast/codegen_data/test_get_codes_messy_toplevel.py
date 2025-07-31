import marimo

app = marimo.App()

# We want a wrapper as a proof of concept. Note, that this will not serialize
# in this form.
def wrapper(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@app.function
def fn(a,
        b, #   hello,
        c,    # again
        d,) -> int:
    # comment
    # another comment

    # yet another comment
    return 0 + a + b + c + d


@wrapper
@app.cell
def wrapped():
    return
