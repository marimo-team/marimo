# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Scale")
    return


@app.cell
def __(mo):
    s = mo.ui.slider(1, 10)
    s
    return s,


@app.cell
def __(mo, s):
    sliders_as_md = mo.md(f"""{s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} {s} """)

    sliders_as_tree = (s,) * 10 + (mo.ui.slider(1, 10),) + (s,) * 10


    sliders_as_nested_tree = mo.as_html(
        [
            mo.as_html([s, s.value]),
            mo.as_html([s, s.value]),
            mo.as_html(
                [
                    mo.as_html([s, s.value]),
                    mo.as_html([s, s.value]),
                    mo.as_html(
                        [
                            mo.as_html([s, s.value]),
                            mo.as_html([s, s.value]),
                        ]
                    ),
                ]
            ),
        ]
    )

    mo.tabs({
        "As MD": sliders_as_md,
        "As Flat Tree": sliders_as_tree,
        "As Nested Tree": sliders_as_nested_tree,
    })
    return sliders_as_md, sliders_as_nested_tree, sliders_as_tree


@app.cell
def __(mo):
    b = mo.ui.button()

    button_as_md = mo.md(
        f"""{b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b} {b}"""
    )

    button_as_tree = (b,) * 10

    mo.tabs(
        {
            "As MD": button_as_md,
            "As Tree": button_as_tree,
        }
    )
    return b, button_as_md, button_as_tree


@app.cell
def __(s):
    [s, s.value]
    return


@app.cell
def __(mo):
    t = mo.ui.text()

    distinct = mo.ui.array(
        [
            mo.ui.text(),
            mo.ui.text(),
            mo.ui.array(
                [
                    mo.ui.text(),
                    mo.ui.text(),
                    mo.ui.array(
                        [
                            mo.ui.text(),
                            mo.ui.text(),
                            mo.ui.array([mo.ui.text(), mo.ui.text()]),
                        ]
                    ),
                ]
            ),
        ]
    )

    same = mo.ui.array(
        [
            t,
            t,
            mo.ui.array(
                [
                    t,
                    t,
                    mo.ui.array(
                        [
                            t,
                            t,
                            mo.ui.array([t, t]),
                        ]
                    ),
                ]
            ),
        ]
    )

    mo.hstack([same, distinct])
    return distinct, same, t


@app.cell
def __():
    return


@app.cell
def __(mo):
    mo.md(
        """
    ---

    # h1 Heading
    ## h2 Heading
    ### h3 Heading
    #### h4 Heading
    ##### h5 Heading
    ###### h6 Heading


    ## Emphasis

    **This is bold text**

    __This is bold text__

    *This is italic text*

    _This is italic text_

    ~~Strikethrough~~


    ## Blockquotes


    > Blockquotes can also be nested...
    >> ...by using additional greater-than signs right next to each other...
    > > > ...or with spaces between arrows.
    """
    )
    return


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
