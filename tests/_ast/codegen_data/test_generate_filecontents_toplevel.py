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
def fun_that_uses_another():
    return fun_that_uses_mo()


@app.cell
def cell_with_ref_and_def():
    if mo is None:
        var = maybe
    maybe = 1
    return (maybe,)


if __name__ == "__main__":
    app.run()
