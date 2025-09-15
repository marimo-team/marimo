import marimo

__generated_with = "0.15.3"
app = marimo.App(width="medium")

with app.setup():
    def wrapper(fn):
        return fn

    # AST is slightly different when decorator is called
    def called_wrapper():
        return wrapper


@app.function
@wrapper
def my_wrapped():
    pass


@wrapper
@app.function
def inv_wrapped():
    pass


@wrapper
@app.cell
def my_cell():
    pass


# NOTE: This is an invalid case. A cell should never be decorated via codegen,
# However, we capture the case because internal errors should never happen from
# user code.
@app.cell
@wrapper
def inv_cell():
    pass


@app.class_definition
@wrapper
class MyClass:
    pass


@wrapper
@app.class_definition
class InvClass:
    pass


@app.function
@called_wrapper()
def my_wrapped_called():
    pass

@called_wrapper()
@app.function
def inv_wrapped_called():
    pass


@called_wrapper()
@app.cell
def my_cell_called():
    pass

@app.cell
@called_wrapper()
def inv_cell_called():
    pass


@app.class_definition
@called_wrapper()
class MyClassCalled:
    pass


@called_wrapper()
@app.class_definition
class InvClassCalled:
    pass


if __name__ == "__main__":
    app.run()
