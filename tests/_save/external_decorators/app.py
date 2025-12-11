# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///
import marimo

__generated_with = "0.14.16"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo


@app.cell
def decorator_wrap():
    @mo.cache
    def cache(x):
        return x + 1

    bar = cache(1)
    return (bar, cache)


@app.cell
def block_wrap(mo):
    with mo.cache("random") as cache_block:
        x = []

    a = "need a final line to trigger invalid block capture"
    return (x, cache_block)


if __name__ == "__main__":
    app.run()
