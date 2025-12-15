import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo


@app.cell
def _():
    # Standard branch
    x = input("What's your name?") # prefer mo.ui.input in real cases :)
    if len(x) > 20:
        invalid = True
        mo.md("Your name is very long.")
    else:
        invalid = False
        mo.md(f"Nice to meet you {x}")
    return invalid, x


@app.cell
def _(invalid, x):
    # multi if
    if not invalid:
        mo.md(f"User: {x}")
    elif len(x) < 30:
        mo.md(f"Invalid: {x}")
    else:
        mo.md(f"Very Invalid: {x}")
    return


@app.cell
def _(invalid):
    # Single if
    if invalid:
        mo.md("Run the cell again to try again")
    return


@app.cell
def _(invalid, x):
    # Multiply nested cases
    if not invalid:
        if x == "name":
            mo.md("Your name probably isn't name")
    return


@app.cell
def _(x):
    # match and constant cases
    match len(x):
        case 1:
            "Too Short!"
        case _:
            "Maybe reasonable"
    return


@app.cell
def _(invalid):
    # Negative case: print() should NOT be flagged
    if invalid:
        print("Debug message")
    else:
        print("Another debug message")
    return


@app.cell
def _(invalid, mo):
    # Negative case: mo.output.append() should NOT be flagged
    if invalid:
        mo.output.append(mo.md("Error!"))
    else:
        mo.output.append(mo.md("Success!"))
    return


@app.cell
def _(invalid, mo):
    # Negative case: mo.stop() should NOT be flagged
    if invalid:
        mo.stop(True)
    return


@app.cell
def _(invalid):
    import logging
    # Negative case: logging calls should NOT be flagged
    if invalid:
        logging.info("Invalid input")
    else:
        logging.debug("Valid input")
    return


@app.cell
def _(invalid):
    import sys
    # Negative case: sys.stdout.write() should NOT be flagged
    if invalid:
        sys.stdout.write("Error\n")
    else:
        sys.stderr.write("Warning\n")
    return


@app.cell
def _(invalid, mo):
    # Negative case: mo.output.replace() should NOT be flagged
    if invalid:
        mo.output.replace(mo.md("Replaced!"))
    return


if __name__ == "__main__":
    app.run()
