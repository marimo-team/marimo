# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.79"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import random

    return mo, random


@app.cell
def __(mo):
    mo.md("# Basic form")
    return


@app.cell
def __(mo):
    clear_on_submit_input = mo.ui.checkbox(True, label="Clear on submit")
    bordered_input = mo.ui.checkbox(False, label="Bordered")
    show_clear_button_input = mo.ui.checkbox(False, label="Show clear button")
    mo.hstack([clear_on_submit_input, bordered_input, show_clear_button_input])
    return bordered_input, clear_on_submit_input, show_clear_button_input


@app.cell
def __(bordered_input, clear_on_submit_input, mo, show_clear_button_input):
    form_1 = mo.ui.text_area(
        label="Form label", full_width=True, placeholder="Type..."
    ).form(
        submit_button_label="Go!",
        clear_on_submit=clear_on_submit_input.value,
        submit_button_tooltip="Click me",
        bordered=bordered_input.value,
        show_clear_button=show_clear_button_input.value,
    )
    form_1
    return (form_1,)


@app.cell
def __(form_1, mo, random):
    random_number = random.randint(1, 100)
    mo.vstack(
        [
            mo.md("## Basic form value"),
            mo.md(
                f"Random number (to monitor re-renders) **{random_number}**"
            ),
            form_1.value,
        ]
    )
    return (random_number,)


@app.cell
def __(mo):
    mo.md(
        """
    -------

    # Validating forms"""
    )
    return


@app.cell
def __(mo):
    years_experience = mo.ui.slider(1, 10, value=3)
    fn = mo.ui.text()
    ln = mo.ui.text()

    def validate(value):
        if "first_name" not in value or len(value["first_name"]) == 0:
            return "Missing first name"
        if "last_name" not in value or len(value["last_name"]) == 0:
            return "Missing last name"
        if value["years_experience"] < 4:
            return "Must have at least 4 years experience"

    form_2 = (
        mo.md(
            """
        First name: {first_name}

        Last name: {last_name}

        Years Experience: {years_experience}
        """
        )
        .batch(
            first_name=fn,
            last_name=ln,
            years_experience=years_experience,
        )
        .form(
            bordered=False,
            validate=validate,
            show_clear_button=True,
        )
    )

    form_2
    return fn, form_2, ln, validate, years_experience


@app.cell
def __(form_2, mo, random):
    _random_number = random.randint(1, 100)
    mo.vstack(
        [
            mo.md("### Validate form value"),
            mo.md(f"Random number **{_random_number}**"),
            form_2.value,
        ]
    )
    return


@app.cell
def __(mo):
    mo.md(
        """
    ------
    # Dictionary"""
    )
    return


@app.cell
def __(mo):
    dict = mo.ui.dictionary(
        {
            "slider": mo.ui.slider(1, 10),
            "text": mo.ui.text("type something!"),
            "array": mo.ui.array(
                [
                    mo.ui.button(value=0, on_click=lambda v: v + 1)
                    for _ in range(3)
                ],
                label="buttons",
            ),
        }
    )
    dict
    return (dict,)


@app.cell
def __(dict, mo):
    mo.vstack(
        [
            mo.md("## Dictionary Value"),
            dict.value,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
