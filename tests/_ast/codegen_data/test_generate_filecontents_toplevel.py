# This comment should be preserved.

# The best way to regenerate this file is open it up
# in the editor. i.e:
#     marimo edit tests/_ast/codegen_data/test_generate_filecontents_toplevel.py

import marimo

__generated_with = "0.0.0"
app = marimo.App()

with app.setup:
    import io
    import textwrap
    import typing
    from pathlib import Path
    import dataclasses

    import marimo as mo


@app.cell
def _():
    shadow = 1
    globe = 1
    (
        fun_that_uses_mo(),
        fun_that_uses_another(),
        fun_that_uses_another_but_out_of_order(),
    )
    return globe, shadow


@app.function
# Sanity check that base case works.
def addition(a, b):
    return a + b


@app.function
def shadow_case(shadow):
    shadow = 2
    return shadow


@app.cell
def _(shadow):
    def reference_case():
        return shadow
    return


@app.cell
def _(globe):
    def global_case():
        global globe
        return globe
    return


@app.function
def fun_that_uses_mo():
    return mo.md("Hello there!")


@app.function
def fun_that_uses_another_but_out_of_order():
    return fun_that_uses_another()


@app.function
def fun_uses_file():
    # file is in globals but not builtins
    return __file__


@app.function
def fun_that_uses_another():
    return fun_that_uses_mo()


@app.cell
def cell_with_ref_and_def():
    if mo is None:
        var = maybe
    maybe = 1
    return (maybe,)


@app.cell
def _():
    # Trailing comments should break function serialization.
    def addition_with_trailing_comments(a, b):
        return a + b
    # This is a comment
    return


@app.class_definition
@dataclasses.dataclass
class ExampleClass:
    ...


@app.class_definition
class SubClass(ExampleClass):
    ...


if __name__ == "__main__":
    app.run()
