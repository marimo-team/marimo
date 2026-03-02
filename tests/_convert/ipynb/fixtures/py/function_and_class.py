import marimo

__generated_with = "0.19.2"
app = marimo.App()


@app.cell
def _():
    x = 1
    return


@app.function
def add(a, b):
    return a + b


@app.function(hide_code=True)
def subtract(a, b):
    return a - b


@app.class_definition
class MyClass:
    def __init__(self, val):
        self.val = val
    def double(self):
        return self.val * 2


@app.class_definition(hide_code=True)
class HiddenClass:
    def __init__(self, val):
        self.val = val


if __name__ == "__main__":
    app.run()
