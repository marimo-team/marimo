# Copyright 2026 Marimo. All rights reserved.

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    mo.md(r"""
    # Internal error reporting

    This notebook intentionally raises three independent errors. Run all cells
    in edit mode using a checkout with the reporting feature and its frontend.

    1. **Marimo internal error:** offers **Report a marimo bug**.
    2. **User ValueError:** has no marimo bug report button.
    3. **User-defined InternalError:** also has no marimo bug report button.

    Open the report from the first error and check:

    - The environment details load and the selected error and traceback appear.
    - **Include errors** starts checked; unchecking it removes errors from the
      GitHub issue link.
    - **Include notebook code** starts unchecked with a fresh browser preference.
      Checking it adds the notebook source to the issue link.
    - Review the prefilled GitHub form without submitting an issue.
    - The general **Report an issue** dialog starts with **Include errors**
      unchecked, even after using the contextual report.
    """)
    return


@app.cell
def marimo_internal_error():
    from marimo._core.errors import InternalError as _MarimoInternalError

    raise _MarimoInternalError("Intentional marimo error for report testing")
    return


@app.cell
def user_value_error():
    raise ValueError("Intentional user error: no marimo bug report button")
    return


@app.cell
def user_internal_error():
    class InternalError(RuntimeError):
        pass

    raise InternalError("User-defined InternalError: no marimo bug report button")
    return


if __name__ == "__main__":
    app.run()
