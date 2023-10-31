# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.39"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import random
    return mo, random


@app.cell
def __(mo):
    form_1 = mo.ui.text_area(label="Form 1").form()
    form_1
    return form_1,


@app.cell
def __(form_1, mo, random):
    random_number = random.randint(1, 100)
    mo.vstack(
        [
            mo.md("### Form 1 Value"),
            mo.md(f"Random number **{random_number}**"),
            form_1.value,
        ]
    )
    return random_number,


@app.cell
def __(mo):
    fn = mo.ui.text()
    ln = mo.ui.text()
    return fn, ln


@app.cell
def __(fn, ln, mo):
    years_experience = mo.ui.slider(1, 10, value=4)
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
        .form()
    )

    form_2
    return form_2, years_experience


@app.cell
def __(form_2, mo, random):
    _random_number = random.randint(1, 100)
    mo.vstack(
        [
            mo.md("### Form 2 Value"),
            mo.md(f"Random number **{_random_number}**"),
            form_2.value,
        ]
    )
    return


@app.cell
def __(mo):
    mo.md("## Dictionary")
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
    return dict,


@app.cell
def __(dict, mo):
    mo.vstack(
        [
            mo.md("### Dict Value"),
            dict.value,
        ]
    )
    return


if __name__ == "__main__":
    app.run()
