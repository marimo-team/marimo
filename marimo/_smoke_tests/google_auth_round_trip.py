# Copyright 2026 Marimo. All rights reserved.

"""Smoke test for ``sys.stdin._request_auth``.

Exercises the kernel->frontend->kernel round-trip plumbing for the
auth-request stdin channel. The frontend renders ``AuthRequest.tsx``
(stub) which returns a canned JSON token envelope on click.

Run with the round-trip tracer enabled:

    MARIMO_AUTH_DEBUG_LOG=/path/to/your.log \\
        marimo edit marimo/_smoke_tests/google_auth_round_trip.py

Then click "Sign in (Phase 0 stub)" and inspect the log file + the
returned dict in the notebook output.

DEVELOPER USE ONLY — DO NOT SHARE NOTEBOOK OUTPUT
-------------------------------------------------
This smoke test deliberately prints the full request payload and
response (including any ``access_token`` field) into the notebook
output for round-trip debugging. **Do not paste the rendered
notebook into a bug report, support ticket, customer-facing chat,
or any shared document.** Use it locally against the Phase-0 stub
token (``FAKE_PHASE_0_TOKEN``) or expect to redact the
``access_token`` field by hand before sharing.

Production-default logging in ``marimo/_messaging/streams.py`` and
``packages/marimo-google-auth/.../_bridge.py`` already records only
byte counts (never token contents); this notebook is the only place
that surfaces the raw response, and it does so on purpose.
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import sys
    import time
    import uuid

    return json, sys, time, uuid


@app.cell
def _(mo):
    mo.md(r"""
    # `sys.stdin._request_auth` round-trip smoke test

    Click the **Sign in (Phase 0 stub)** button below when it appears.
    The kernel-side call will unblock and the next cell will display the
    canned response.

    /// warning | Developer use only

    This notebook prints the full request payload and response —
    **including any `access_token` field** — into the output for
    debugging. Do **not** share the rendered notebook (screenshots,
    HTML export, pasted output) outside the development environment.
    The Phase-0 stub returns ``FAKE_PHASE_0_TOKEN`` so this is safe
    locally; running against a real token-issuing frontend would
    surface the live token.
    ///
    """)
    return


@app.cell
def _(json, sys, time, uuid):
    request_id = str(uuid.uuid4())
    payload = json.dumps(
        {
            "protocol_version": 1,
            "request_id": request_id,
            "provider": "google",
            "scopes": [
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
            "include_granted_scopes": True,
            "hosted_domain": None,
        }
    )
    t0 = time.time()
    raw_response = sys.stdin._request_auth(payload)
    elapsed_ms = (time.time() - t0) * 1000.0
    response = json.loads(raw_response)
    return elapsed_ms, payload, raw_response, request_id, response


@app.cell
def _(elapsed_ms, mo, payload, raw_response, request_id, response):
    mo.md(f"""
    ## Round-trip result

    - **request_id:** `{request_id}`
    - **elapsed:** `{elapsed_ms:.1f} ms`
    - **response.status:** `{response.get("status")}`
    - **response.access_token:** `{response.get("access_token")}`
    - **scopes echoed back:** `{response.get("scope")}`

    ### Raw payload sent
    ```json
    {payload}
    ```

    ### Raw response received
    ```json
    {raw_response}
    ```
    """)
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


if __name__ == "__main__":
    app.run()
