# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi",
#     "marimo",
#     "starlette",
#     "jinja2",
#     "itsdangerous",
#     "python-dotenv",
#     "python-multipart",
#     "passlib",
#     "pydantic",
#     "vega-datasets==0.9.0",
# ]
# ///

# Copyright 2026 Marimo. All rights reserved.
from pathlib import Path
from typing import Annotated, Callable, Coroutine
from fastapi.responses import HTMLResponse, RedirectResponse
import marimo
from fastapi import FastAPI, Form, Request, Response

dirname = Path(__file__).parent.parent

server = (
    marimo.create_asgi_app()
    # Mount the dataframe app at /dataframes
    .with_app(path="/dataframes", root=str(dirname / "dataframe.py"))
    # Mount the ansi app at /ansi
    .with_app(path="/ansi", root=str(dirname / "ansi.py"))
    # Mount directory at /data
    # You can visit /charts/altair_brush/
    # You can visit /charts/altair_polars/
    .with_dynamic_directory(path="/chart", directory=str(dirname / "altair"))
    .with_dynamic_directory(path="/smoke_tests", directory=str(dirname))
    # Mount the buttons app at the root
    .with_app(path="", root=str(dirname / "buttons.py"))
)

# Create a FastAPI app
app = FastAPI()


# Super simple auth middleware
# If no token, redirect to login page with simple form
# Any password is valid for a token
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
async def root():
    return {"message": "pong"}

@app.get("/")
async def root():
    return HTMLResponse(
        """
        <h1>Choose an application</h1>
        <a href="/dataframes">Dataframes</a>
        <a href="/ansi">Ansi</a>
        <a href="/charts/altair_brush/">Chart</a>
        """
    )

app.mount("/", server.build())

# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")
