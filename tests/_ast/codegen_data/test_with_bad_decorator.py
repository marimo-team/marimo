import marimo

__generated_with = "0.0.0"
app = marimo.App()


@app.function
def wrap(f) -> int:
    return 100

@app.function
@wrap
def hundred(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    app.run()
