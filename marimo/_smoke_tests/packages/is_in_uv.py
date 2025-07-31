import marimo

__generated_with = "0.13.11"
app = marimo.App(width="medium")


@app.cell
def _():
    import os
    from pathlib import Path

    # Check we have a virtual environment
    venv_path = os.environ.get("VIRTUAL_ENV", None)
    # Check that the `UV` environment variable is set
    # This tells us that marimo was run by uv
    uv_env_exists = os.environ.get("UV", None)
    # Check that the uv.lock and pyproject.toml files exist
    uv_lock_path = Path(venv_path).parent / "uv.lock"
    pyproject_path = Path(venv_path).parent / "pyproject.toml"

    # If all these are True or defined, then we are running in a uv project
    {
        "venv_path": venv_path,
        "uv_env_exists": uv_env_exists,
        "uv_lock_path": uv_lock_path.exists(),
        "pyproject_path": pyproject_path.exists(),
    }
    return


if __name__ == "__main__":
    app.run()
