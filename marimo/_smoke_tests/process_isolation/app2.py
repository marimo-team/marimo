# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///
import marimo

__generated_with = "0.13.0"
app = marimo.App()


@app.cell
def _():
    import sys
    from pathlib import Path

    # Add our own modules directory to sys.path so `import shared_module`
    # resolves to OUR version of the module.
    _modules_dir = str(Path(__file__).parent / "app2_modules")
    if _modules_dir not in sys.path:
        sys.path.insert(0, _modules_dir)

    # Both app1 and app2 do `import shared_module` — same top-level name,
    # different directories. Without process isolation, whichever loads
    # first wins (the other gets the wrong module from sys.modules cache).
    import shared_module  # noqa: E402

    identity = shared_module.get_identity()
    return (identity, shared_module)


@app.cell
def _(identity, shared_module):
    import os
    import threading

    import marimo as mo

    pid = os.getpid()
    tid = threading.get_ident()

    expected_app = "app2"
    expected_magic = 222

    is_correct = (
        identity["app"] == expected_app and identity["magic"] == expected_magic
    )

    if is_correct:
        status = mo.md(
            f"""
            ## App 2 — Process Isolation: PASS

            | Field | Value | Expected |
            |-------|-------|----------|
            | `APP_NAME` | `{identity['app']}` | `{expected_app}` |
            | `MAGIC_NUMBER` | `{identity['magic']}` | `{expected_magic}` |
            | `__file__` | `{shared_module.__file__}` | — |
            | `PID` | `{pid}` | — |
            | `Thread ID` | `{tid}` | — |
            """
        ).callout(kind="success")
    else:
        status = mo.md(
            f"""
            ## App 2 — Process Isolation: FAIL

            | Field | Value | Expected |
            |-------|-------|----------|
            | `APP_NAME` | `{identity['app']}` | `{expected_app}` |
            | `MAGIC_NUMBER` | `{identity['magic']}` | `{expected_magic}` |
            | `__file__` | `{shared_module.__file__}` | — |
            | `PID` | `{pid}` | — |
            | `Thread ID` | `{tid}` | — |

            **Module clash!** Got another app's `shared_module`.
            """
        ).callout(kind="danger")

    status
    return


if __name__ == "__main__":
    app.run()
