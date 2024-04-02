# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.3"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    slider = mo.ui.slider(1, 10, label="Slider")
    debounced_slider = mo.ui.slider(1, 10, debounce=True, label="Debounced Slider")

    number = mo.ui.number(1, 10, label="Number")
    debounced_number = mo.ui.number(1, 10, debounce=True, label="Debounced Number")
    return debounced_number, debounced_slider, number, slider


@app.cell
def __(debounced_number, debounced_slider, mo, number, slider):
    mo.md(f"""
        Controls:

        {slider}

        {debounced_slider}

        {number}

        {debounced_number}
    """)
    return


@app.cell
def __(debounced_number, debounced_slider, mo, number, slider):
    # Values
    mo.md(f"""    
        slider: {slider.value}

        debounced slider: {debounced_slider.value}

        number: {number.value}

        debounced number: {debounced_number.value}
    """)
    return


@app.cell
def __(debounced_number, debounced_slider, mo, number, slider):
    mo.md(f"""
        Controls and Values:

        {slider} -> {slider.value}

        {debounced_slider} -> {debounced_slider.value}

        {number} -> {number.value}

        {debounced_number} -> {debounced_number.value}
    """)
    return


if __name__ == "__main__":
    app.run()
