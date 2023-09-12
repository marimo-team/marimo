import marimo

__generated_with = "0.1.8"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    disabled = mo.ui.switch(label="Disabled")
    mo.hstack([disabled])
    return disabled,


@app.cell
def __(disabled, mo):
    mo.vstack(
        [
            mo.ui.text(label="Your name", min_length=1, disabled=disabled.value),
            mo.ui.text(
                label="Your tagline", max_length=30, disabled=disabled.value
            ),
            mo.ui.text_area(
                label="Your bio", max_length=180, disabled=disabled.value
            ),
        ]
    )
    return


@app.cell
def __(disabled, mo):
    mo.ui.text(
        label="At least 10 characters", min_length=10, disabled=disabled.value
    ).form()
    return


if __name__ == "__main__":
    app.run()
