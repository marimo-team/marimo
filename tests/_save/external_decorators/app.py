import marimo

__generated_with = "0.14.16"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo


@app.cell
def _():
    @mo.cache
    def cache(x):
        return x + 1

    bar = cache(1)
    return (bar, cache)


if __name__ == "__main__":
    app.run()
