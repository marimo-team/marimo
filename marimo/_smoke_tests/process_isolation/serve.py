# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "pyzmq",
#     "starlette",
#     "uvicorn",
# ]
# [tool.uv.sources]
# marimo = {path = "../../..", editable = true}
# ///

"""Smoke test for per-app worker process isolation.

This script serves two notebooks (app1.py and app2.py) that each import a
module named `shared_module` — but from different directories with different
contents. Without process isolation, whichever app loads `shared_module`
first would win, and the other app would get the wrong module. With process
isolation, each app runs in its own OS process, so `sys.modules` is not shared.

Usage (pick one):

    # Option 1: create_asgi_app() — always uses process isolation
    python marimo/_smoke_tests/process_isolation/serve.py

    # Option 2: marimo run with multiple files — auto-enables process isolation
    marimo run marimo/_smoke_tests/process_isolation/app1.py \
               marimo/_smoke_tests/process_isolation/app2.py

Then open:
    - http://localhost:8000/app1/ — should show "PASS" with APP_NAME=app1
    - http://localhost:8000/app2/ — should show "PASS" with APP_NAME=app2

If both show PASS, process isolation is working correctly.
If either shows FAIL, the module clash bug is present.
"""

from pathlib import Path

import marimo
import uvicorn

here = Path(__file__).parent

app = (
    marimo.create_asgi_app()
    .with_app(path="/app1", root=str(here / "app1.py"))
    .with_app(path="/app2", root=str(here / "app2.py"))
    .build()
)

if __name__ == "__main__":
    print(__doc__)
    uvicorn.run(app, host="localhost", port=8000, log_level="info")
