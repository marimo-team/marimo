# Regression test for https://github.com/marimo-team/marimo/issues/5129
# mo.lazy inside mo.ui.tabs should only execute the function once.
# Previously, the shadow DOM created a duplicate marimo-lazy element
# which fired a second load() request.

import marimo

__generated_with = "0.13.14"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    def lazy_tab():
        import time

        print("LAZYTAB 1")
        time.sleep(1)
        print("LAZYTAB 2")
        return mo.md("Finish loading lazy tab !")

    mo.ui.tabs(
        {
            "normal-tab": mo.md("This is a normal tab"),
            "lazy-tab": mo.lazy(lazy_tab),
        }
    )
    return


if __name__ == "__main__":
    app.run()
