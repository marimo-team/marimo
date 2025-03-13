import marimo

__generated_with = "0.11.19"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    # Commented out because doesn't surface other errors; uncomment to surface.

    # # mixed indentation
    # def bad_indentation():
    #     print("correct")
    #         print("wrong")
    return


app._unparsable_cell(
    r"""
    # fmt: off
    import os
    import sys
    from typing import List, Dict
    import random

    # undefined variable
    result = undefined_var + 10

    # unused import
    import json

    # unused variable
    unused_variable = 42

    # missing type hints
    def add_numbers(a, b):
        return a + b

    # undefined name
    print(nonexistent_variable)

    # too many blank lines




    # missing docstring
    class MyClass:
        def __init__(self):
            self.value = 10

    # unused method parameter
    def process_data(data, unused_param):
        return data * 2

    # variable shadowing
    def shadow_test():
        x = 5
        for x in range(3):
            print(x)

    # mutable default argument
    def risky_function(items=[]):
        items.append(1)
        return items

    # star imports
    from os import *

    # too many arguments
    def too_many_args(a,b,c,d,e,f,g,h,i,j,k):
        return a+b

    # bare except
    try:
        risky_operation()
    except:
        pass

    # redefining built-in
    list = []
    str = \"hello\"
    def print():
        pass

    # missing final newline

    # line too long
    very_long_variable_name = \"This is an extremely long line that exceeds the recommended maximum line length and should trigger a linting warning\"

    # multiple statements on one line
    x = 5; y = 10; z = 15

    # complex boolean expression
    if x == True and y == False and z == True and zz == False:
        pass

    # wrong variable name style
    camelCaseVariable = 123

    # undefined name in type annotation
    def process_items(items: InvalidType) -> None:
        pass

     # fmt: on
    """,
    name="_"
)


if __name__ == "__main__":
    app.run()
