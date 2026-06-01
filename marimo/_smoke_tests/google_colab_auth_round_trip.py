# Copyright 2026 Marimo. All rights reserved.
#
# NOTE: No `# /// script` header on purpose. The companion package
# `marimo-google-auth` is an editable install in the marimo dev venv and
# is not (yet) on PyPI, so uv-sandboxed isolation would fail to resolve
# it. Run this notebook from the marimo dev venv directly:
#
#     MARIMO_AUTH_DEBUG_LOG=/path/to/your.log \
#         .venv/bin/marimo edit marimo/_smoke_tests/google_colab_auth_round_trip.py
#
# When `marimo-google-auth` ships to PyPI this header can be restored.

"""Phase-1 smoke test for the ``marimo-google-auth`` package.

Exercises the full chain against the Phase-0 frontend stub:

  user code
    -> `from google.colab import auth` (installs pydata patch)
    -> `auth.authenticate_user(scopes=...)`
        -> `_bridge.request_auth(scopes)`
            -> `sys.stdin._request_auth(...)`  (marimo kernel)
                -> frontend AuthRequest stub (returns canned FAKE token)
        -> `_adc.write_adc(...)`
    -> returns Credentials with `.token = FAKE_PHASE_0_TOKEN`

Then proves the pydata-google-auth patch is wired:

  `pydata_google_auth.get_user_credentials([...])` should funnel through
  our patch and return the same credential without ever opening a
  localhost web server.

To run with tracing:

    MARIMO_AUTH_DEBUG_LOG=/path/to/your.log \\
        marimo edit marimo/_smoke_tests/google_colab_auth_round_trip.py

Click the "Sign in (Phase 0 stub)" button when the cells block.

DEVELOPER USE ONLY — DO NOT SHARE NOTEBOOK OUTPUT
-------------------------------------------------
Each cell renders ``creds.token`` directly into the notebook output
for round-trip verification. Against the Phase-0 stub this prints
``FAKE_PHASE_0_TOKEN`` and is harmless to share. Against any
non-stub frontend (Phase 2+) the same cells would print a **real
Google access token**. Do not export, screenshot, or paste the
rendered notebook outside the development environment without
redacting the ``token`` fields.
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(r"""
    # `marimo-google-auth` Phase 1 smoke test

    Click **Sign in (Phase 0 stub)** each time a cell blocks waiting
    for auth. The patched flow should mint a `Credentials` object
    from a canned token without ever opening `localhost:8080`.

    /// warning | Developer use only

    The cells below print the raw `creds.token`. Against the Phase-0
    stub this is ``FAKE_PHASE_0_TOKEN`` (safe). Against a Phase-2+
    frontend this is a **real Google access token** — do not share
    the rendered notebook in bug reports, screenshots, or chat
    without redacting the `token` fields.
    ///
    """)
    return


@app.cell
def _():
    from google.colab import auth

    return (auth,)


@app.cell
def _(auth, mo):
    creds = auth.authenticate_user(
        _marimo_scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
    )
    out = mo.md(
        f"""
        ## Direct `authenticate_user` call

        - **token:** `{creds.token}`
        - **scopes:** `{creds.scopes}`
        - **expiry:** `{creds.expiry}`
        """
    )
    return creds, out


@app.cell
def _(out):
    out
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Cached-call check

    The next cell calls `authenticate_user` again with the same
    scopes. With the in-process cache active, no new round-trip
    should occur — i.e. you should **not** see the stub button.
    """)
    return


@app.cell
def _(auth):
    cached_creds = auth.authenticate_user(
        _marimo_scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
    )
    return (cached_creds,)


@app.cell
def _(cached_creds, creds, mo):
    mo.md(f"""
    - **same token as before:** `{cached_creds.token == creds.token}`
    - **token:** `{cached_creds.token}`
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## `pydata-google-auth` patch verification

    Calling `pydata_google_auth.get_user_credentials` should hit
    our patched `get_colab_default_credentials` first and return
    the canned credential without trying `run_local_server`.
    """)
    return


@app.cell
def _():
    import pydata_google_auth

    pga_creds = pydata_google_auth.get_user_credentials(
        scopes=["https://www.googleapis.com/auth/drive"],
        use_local_webserver=True,
    )
    return (pga_creds,)


@app.cell
def _(mo, pga_creds):
    mo.md(f"""
    - **token:** `{pga_creds.token}`
    - **scopes:** `{pga_creds.scopes}`
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## `google.auth.default()` check

    With our ADC file written, `google.auth.default()` should be
    able to load credentials (it'll find our authorized_user JSON
    with the canned access token).
    """)
    return


@app.cell
def _():
    import google.auth

    default_creds, project = google.auth.default()
    return default_creds, project


@app.cell
def _(default_creds, mo, project):
    mo.md(f"""
    - **default_creds type:** `{type(default_creds).__name__}`
    - **project:** `{project!r}`
    - **valid:** `{default_creds.valid if hasattr(default_creds, "valid") else "n/a"}`
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
