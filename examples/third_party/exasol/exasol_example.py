# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "marimo",
#     "pyexasol",
#     "pandas",
#     "sqlalchemy",
#     "sqlalchemy-exasol",
# ]
# ///

import marimo

__generated_with = "0.19.2"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Exasol with `pyexasol`

    [Exasol](https://www.exasol.com/) is a high-performance analytics database.
    [pyexasol](https://github.com/exasol/pyexasol) is the official Python driver
    using a WebSocket connection.

    ## Prerequisites

    You need a running Exasol database. If you don't have one, you can spin up
    a free instance using Docker — see
    [exasol/docker-db](https://github.com/exasol/docker-db) for setup instructions.

    Then run this notebook:

    ```bash
    uvx marimo edit --sandbox exasol_example.py
    ```
    """)
    return


@app.cell
def _():
    import marimo as mo
    import pyexasol
    return mo, pyexasol


@app.cell
def _(mo):
    cred_form = (
        mo.md(
            """
            ### Connect to Exasol

            | | |
            | -- | -- |
            | **Connection name** | {db_name} |
            | **Host:Port** | {host} |
            | **User** | {user} |
            | **Password** | {password} |
            | **Fingerprint** | {fingerprint} |
            | **Certificate check** | {cert_check} |
            """
        )
        .batch(
            db_name=mo.ui.text(placeholder="my_exasol", full_width=True),
            host=mo.ui.text(placeholder="localhost:8563", full_width=True),
            user=mo.ui.text(placeholder="username", full_width=True),
            password=mo.ui.text(kind="password", full_width=True),
            fingerprint=mo.ui.text(placeholder="(optional) hex or nocertcheck", kind="password", full_width=True),
            cert_check=mo.ui.radio(options={"Verify": True, "Disable (not recommended for Prod environments)": False}, value="Disable (not recommended for Prod environments)"),
        )
        .form(submit_button_label="Connect")
    )
    cred_form
    return (cred_form,)


@app.cell
def _(cred_form, mo, pyexasol):
    mo.stop(cred_form.value is None, mo.md("_Fill in credentials and click **Connect**._"))

    _host_port = cred_form.value["host"]
    _fp = cred_form.value["fingerprint"]
    if _fp:
        _dsn = f"{_host_port.split(':')[0]}/{_fp}:{_host_port.split(':')[1]}"
    elif not cred_form.value["cert_check"]:
        _dsn = f"{_host_port.split(':')[0]}/nocertcheck:{_host_port.split(':')[1]}"
    else:
        _dsn = _host_port

    conn = pyexasol.connect(
        dsn=_dsn,
        user=cred_form.value["user"],
        password=cred_form.value["password"],
        encryption=True,
    )
    mo.md("**Connected!**")
    return (conn,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run a query
    """)
    return


@app.cell
def _(conn):
    df = conn.export_to_pandas("SELECT * FROM EXA_ALL_SCHEMAS ORDER BY SCHEMA_NAME")
    df
    return (df,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Browse tables in a schema
    """)
    return


@app.cell
def _(df, mo):
    schema_dropdown = mo.ui.dropdown(
        options=df["SCHEMA_NAME"].tolist(),
        label="Schema",
    )
    schema_dropdown
    return (schema_dropdown,)


@app.cell
def _(conn, schema_dropdown):
    tables = conn.export_to_pandas(
        f"""
        SELECT TABLE_NAME, TABLE_ROW_COUNT
        FROM EXA_ALL_TABLES
        WHERE TABLE_SCHEMA = '{schema_dropdown.value}'
        ORDER BY TABLE_NAME
        """
    ) if schema_dropdown.value else None
    tables
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Connect with SQLAlchemy

    You can also use [SQLAlchemy](https://docs.marimo.io/guides/working_with_data/sql/#2-using-code)
    with the `sqlalchemy-exasol` dialect. Marimo auto-discovers any
    `sqlalchemy.engine.Engine` in your namespace and makes it available
    in the SQL cell connection dropdown.
    """)
    return


@app.cell
def _(cred_form, mo):
    mo.stop(cred_form.value is None)

    import sqlalchemy

    _dsn = cred_form.value["host"]
    _host, _port = _dsn.split(":") if ":" in _dsn else (_dsn, "8563")
    _fp = cred_form.value["fingerprint"]
    _query = {}
    if _fp:
        _query["FINGERPRINT"] = _fp
    elif not cred_form.value["cert_check"]:
        _query["FINGERPRINT"] = "nocertcheck"

    _url = sqlalchemy.engine.URL.create(
        drivername="exa+websocket",
        username=cred_form.value["user"],
        password=cred_form.value["password"],
        host=_host,
        port=int(_port),
        database=cred_form.value["db_name"],
        query=_query,
    )
    exasol = sqlalchemy.create_engine(_url, connect_args={"schema": ""})
    exasol
    return (exasol,)


@app.cell
def _(exasol, mo):
    _result = mo.sql(
        f"""
        SELECT CURRENT_TIMESTAMP AS now, 'Hello from SQLAlchemy!' AS greeting
        """,
        engine=exasol
    )
    return


if __name__ == "__main__":
    app.run()
