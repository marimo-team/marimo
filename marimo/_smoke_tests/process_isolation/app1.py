# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "humanize",
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
    _modules_dir = str(Path(__file__).parent / "app1_modules")
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

    expected_app = "app1"
    expected_magic = 111

    is_correct = (
        identity["app"] == expected_app and identity["magic"] == expected_magic
    )

    if is_correct:
        status = mo.md(
            f"""
            ## App 1 — Process Isolation: PASS

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
            ## App 1 — Process Isolation: FAIL

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

    print("HELLO FROM APP 1")

    status
    return


@app.cell
def _():
    in_sandbox = sys.prefix != sys.base_prefix

    # Try importing the sandbox-only dep for this app
    sandbox_dep_ok = False
    try:
        import humanize

        sandbox_dep_ok = True
        dep_info = f"`humanize` {humanize.__version__}"
    except ImportError:
        dep_info = "`humanize` not installed"

    # Check that the OTHER app's sandbox dep is NOT available
    other_dep_leaked = False
    try:
        import pyfiglet  # noqa: F401

        other_dep_leaked = True
    except ImportError:
        pass

    if in_sandbox:
        if sandbox_dep_ok and not other_dep_leaked:
            sandbox_status = mo.md(
                f"""
                ## App 1 — Sandbox: PASS

                | Field | Value |
                |-------|-------|
                | `sys.executable` | `{sys.executable}` |
                | `sys.prefix` | `{sys.prefix}` |
                | Sandbox dep | {dep_info} |
                | Other app's dep leaked? | No |
                """
            ).callout(kind="success")
        else:
            sandbox_status = mo.md(
                f"""
                ## App 1 — Sandbox: FAIL

                | Field | Value |
                |-------|-------|
                | `sys.executable` | `{sys.executable}` |
                | `sys.prefix` | `{sys.prefix}` |
                | Sandbox dep | {dep_info} |
                | Other app's dep leaked? | {"Yes" if other_dep_leaked else "No"} |
                """
            ).callout(kind="danger")
    else:
        sandbox_status = mo.md(
            f"""
            ## App 1 — Not running in sandbox mode

            `sys.executable`: `{sys.executable}`

            Run with `--sandbox` to test sandbox isolation.
            """
        ).callout(kind="warn")

    sandbox_status
    return


if __name__ == "__main__":
    app.run()
