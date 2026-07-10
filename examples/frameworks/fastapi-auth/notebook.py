import marimo

__generated_with = "0.20.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    req = mo.app_meta().request
    user = req.user if req else None
    meta = req.meta if req else None

    mo.md(f"""
    ## User info from `mo.app_meta().request`

    - **user**: `{user}`
    - **username**: `{user['username'] if isinstance(user, dict) else 'N/A'}`
    - **meta**: `{meta}`
    """)
    return


if __name__ == "__main__":
    app.run()
