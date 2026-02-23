# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi",
#     "starlette",
#     "jinja2",
#     "itsdangerous",
#     "python-dotenv",
#     "python-multipart",
#     "passlib",
#     "pydantic",
#     "marimo",
#     "polars",
#     "pandas",
#     "altair",
#     "vega-datasets==0.9.0",
# ]
# [tool.uv.sources]
# marimo = {path = "../../..", editable = true}
# ///

# Smoke test for marimo ASGI integration with FastAPI.
# Tests two mount scenarios:
#   1. Root mount ("/") — server1 with static apps + dynamic directories
#   2. Sub-path mount ("/app2") — server2 with dynamic directory
#      (reproduces GitHub issue #8322)
#
# Run with: uv run --script my_server.py

from pathlib import Path
from typing import Annotated, Callable, Coroutine

import marimo
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

dirname = Path(__file__).parent.parent

# Server 1: Root-mounted ASGI app demonstrating multiple mount patterns
# This server showcases:
#   - Static app mounting with .with_app() at specific paths
#   - Dynamic directory mounting with .with_dynamic_directory() for entire folders
#   - Root-level app ("") that serves when no other path matches
# All routes are relative to the root "/" since this is mounted at the root.
server1 = (
    marimo.create_asgi_app()
    # Static app mounts: single notebooks served at fixed paths
    .with_app(path="/dataframes", root=str(dirname / "dataframe.py"))
    .with_app(path="/ansi", root=str(dirname / "ansi.py"))
    # Dynamic directory mount: entire folder becomes browsable/runnable
    # Example: altair_brush.py in altair_examples/ → /charts/altair_brush/
    .with_dynamic_directory(
        path="/charts", directory=str(dirname / "altair_examples")
    )
    # Another dynamic directory: all notebooks in parent directory
    .with_dynamic_directory(path="/smoke_tests", directory=str(dirname))
    # Root app: serves at "/" when server1 is mounted (acts as default/home)
    .with_app(path="", root=str(dirname / "buttons.py"))
)

# Server 2: Sub-path mounted ASGI app (regression test for issue #8322)
# This server tests the critical edge case where the ASGI app is mounted
# at a sub-path (e.g., "/server2") rather than root. Previously, this caused
# routing conflicts when dynamic directories used paths matching the mount point.
# Key test: dynamic directory at "/" relative to mount = "/server2/" absolute
server2 = (
    marimo.create_asgi_app()
    # Dynamic directory at sub-path: /apps becomes /server2/apps in FastAPI
    .with_dynamic_directory(
        path="/apps", directory=str(dirname / "altair_examples")
    )
)

app = FastAPI()


# Super simple auth middleware
@app.middleware("http")
async def auth_middleware(
    request: Request,
    call_next: Callable[[Request], Coroutine[None, None, Response]],
) -> Response:
    if request.url.path == "/login":
        response = await call_next(request)
        return response
    if "token" not in request.cookies:
        return RedirectResponse(url="/login")
    return await call_next(request)


@app.get("/login")
async def get_login():
    return HTMLResponse(
        """
        <form action="/login" method="post">
            <label for="token">Token</label>
            <input type="text" id="token" name="token">
            <button type="submit">Submit</button>
        </form>
        """
    )


@app.post("/login")
async def post_login(token: Annotated[str, Form()]):
    response = RedirectResponse(url="/")
    response.set_cookie(key="token", value=token)
    return response


@app.get("/ping")
async def ping():
    return {"message": "pong"}


@app.get("/")
async def homepage():
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>marimo ASGI Integration Test</title>
            <style>
                body {
                    font-family: system-ui, -apple-system, sans-serif;
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 20px;
                    line-height: 1.6;
                    color: #333;
                }
                h1 { margin-bottom: 8px; }
                h2 { margin-top: 32px; margin-bottom: 8px; font-size: 1.2rem; }
                p { color: #666; margin-bottom: 16px; }
                ul { list-style: none; padding: 0; }
                li { margin: 8px 0; }
                a { color: #0066cc; text-decoration: none; }
                a:hover { text-decoration: underline; }
                code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
                .badge {
                    font-size: 0.75rem;
                    color: #666;
                    margin-left: 8px;
                }
            </style>
        </head>
        <body>
            <h1>marimo ASGI Integration Test</h1>
            <p>Testing FastAPI + marimo ASGI with multiple mount patterns and authentication middleware.</p>

            <h2>Server 1: Root Mount <code>/</code></h2>
            <p>Demonstrates static app mounting and dynamic directory patterns at the root level.</p>
            <ul>
                <li><a href="/dataframes/">Dataframes Example</a> <span class="badge">with_app</span></li>
                <li><a href="/ansi/">ANSI Terminal Colors</a> <span class="badge">with_app</span></li>
                <li><a href="/charts/altair_brush/">Altair Brush Chart</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/charts/altair_charts/">Altair Charts Gallery</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/charts/altair_datetime/">Altair DateTime</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/charts/layered_charts/">Layered Charts</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/charts/boxplot/">Boxplot Example</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/smoke_tests/buttons/">Interactive Buttons</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/smoke_tests/carousel/">Carousel Component</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/smoke_tests/code_editor/">Code Editor</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/smoke_tests/data_explorer/">Data Explorer</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/smoke_tests/dates/">Date Handling</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/smoke_tests/arrays_and_dicts/">Arrays and Dicts</a> <span class="badge">dynamic_directory</span></li>
            </ul>

            <h2>Server 2: Sub-path Mount <code>/server2</code></h2>
            <p>Regression test for GitHub issue #8322 — validates sub-path mounting with dynamic directories.</p>
            <ul>
                <li><a href="/server2/apps/altair_brush/">Altair Brush</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/server2/apps/altair_polars/">Altair Polars</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/server2/apps/altair_geoshape/">Altair Geoshape</a> <span class="badge">dynamic_directory</span></li>
                <li><a href="/server2/apps/hconcat_vconcat/">Chart Concatenation</a> <span class="badge">dynamic_directory</span></li>
            </ul>

            <h2>Additional Endpoints</h2>
            <ul>
                <li><a href="/ping">Ping Health Check</a> <span class="badge">API</span></li>
            </ul>
        </body>
        </html>
        """
    )


# Mount server2 first (more specific path)
app.mount("/server2", server2.build())
# Mount server1 at root (catch-all, must be last)
app.mount("/", server1.build())

# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")
