# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "rich",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return


@app.cell
def _():
    # pip install rich
    from rich import print as pprint
    return (pprint,)


@app.cell
def _(pprint):
    pprint("[bold red]Error:[/bold red] Something went wrong!")
    pprint("[green]Success:[/green] Operation completed.")
    return


if __name__ == "__main__":
    app.run()
