import marimo

__generated_with = "0.15.3"
app = marimo.App()

with app.setup():
    def my_decorator(fn):
        return fn


@app.function()
@my_decorator
def my_function():
    x = 1
    return x


if __name__ == "__main__":
    app.run()
