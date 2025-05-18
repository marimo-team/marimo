import marimo

__generated_with = '0.0.0'
app = marimo.App()


with app.setup:
    variable = 1


@app.function
def fn(x: int):
    return x + variable


if __name__ == "__main__":
    app.run()

