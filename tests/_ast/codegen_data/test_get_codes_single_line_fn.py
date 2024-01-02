import marimo

__generated_with = '0.1.0'
app = marimo.App()


@app.cell
def one(a: int, b: int) -> None: c = a + b; print(c); return c,


if __name__ == "__main__":
    app.run()
