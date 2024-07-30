# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.7.12"
app = marimo.App(width="medium")


@app.cell
def __():
    from vega_datasets import data

    cars = data.cars()
    return cars, data


@app.cell
def __(mo):
    size = mo.ui.slider(
        steps=[0, 1, 2, 3],
        value=1,
        label="Size",
    )
    sizes = ["sm", "base", "lg", "2xl"]
    return size, sizes


@app.cell
def __(mo, size, sizes):
    mo.md(f"{size} **{sizes[size.value]}**")
    return


@app.cell
def __(cars, mo):
    mo.md(
        f"""
    # kitchen sink

    ## table

    | col 1 | col 2 | col 3 |
    | --- | --- | --- |
    | 1 | 2 | 3 |
    | 4 | 5 | 6 |

    {mo.as_html(mo.plain(cars))}


    ## code

    ```python
    print("hello world")
    ```


    ## math

    $$
    a^2 + b^2 = c^2
    $$


    ## image

    ![alt text](https://picsum.photos/200/300)

    ## bullets

    - item 1
    - item 2


    ## ordered list

    1. item 1
    2. item 2


    ## blockquote

    > blockquote


    ## link

    [link](https://google.com)

    ## inline code

    `inline code`
    """,
    )
    return


@app.cell
def __():
    {
        "string": "hello",
        "int": 10,
        "float": 10.5,
    }
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
