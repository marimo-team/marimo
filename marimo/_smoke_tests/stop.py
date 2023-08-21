# Copyright 2023 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    import time
    return mo, time


@app.cell
def __(mo):
    secret = mo.ui.text(label="Type a valid password: ")
    secret
    return secret,


@app.cell
def __(mo, secret):
    # Validation 1
    # This cell just depends on the secret
    mo.stop(
        len(secret.value) < 8, mo.md("Must have length 8").callout(kind="warn")
    )

    success_1 = True
    return success_1,


@app.cell
def __(mo, secret):
    # Validation 2
    # This cell just depends on the secret
    mo.stop(
        "$" not in secret.value, mo.md("Must contain a **$**").callout(kind="warn")
    )

    success_2 = True
    return success_2,


@app.cell
def __(mo, secret, success_1):
    # Validation 3
    # This cell depends on the secret and first validation
    mo.stop(
        "7" not in secret.value and success_1,
        mo.md("Must contain the number 7").callout(kind="warn"),
    )

    success_3 = True
    return success_3,


@app.cell
def __(mo, success_1, success_2, success_3):
    # This depends on all the validations, and not the secret
    _success = success_1 and success_2 and success_3
    mo.stop(not _success)

    mo.md("Secret is correct!").callout(kind="success")
    return


if __name__ == "__main__":
    app.run()
