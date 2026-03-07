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
    import marimo as mo

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

            **Module clash!** Got another app's `shared_module`.
            """
        ).callout(kind="danger")

    status
    return


if __name__ == "__main__":
    app.run()
