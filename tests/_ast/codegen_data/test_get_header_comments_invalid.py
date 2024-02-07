"""Docstring"""

"""
This is an invalid header since there is 
    a statement before the import marmio command
"""

print("Hello World") 

# A copyright license

# A linter/formatter directive

import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one(): return


@app.cell
def two():
    return


if __name__ == "__main__":
    app.run()
