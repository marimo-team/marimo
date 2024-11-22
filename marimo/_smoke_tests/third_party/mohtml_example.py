# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mohtml==0.1.2",
# ]
# ///

import marimo

__generated_with = "0.9.21"
app = marimo.App(width="medium")


@app.cell
def __():
    # You can import any HTML element this way
    from mohtml import a, p, div, script, h1

    div(
        script(src="https://cdn.tailwindcss.com"),
        h1(
            "Testing",
            klass="font-bold text-xl border-yellow-600 border-2 px-2 border-dashed",
        ),
    )
    return a, div, h1, p, script


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
