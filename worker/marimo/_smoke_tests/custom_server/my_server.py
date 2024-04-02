# Copyright 2024 Marimo. All rights reserved.
from typing import Annotated, Callable, Coroutine
from fastapi.responses import HTMLResponse, RedirectResponse
import marimo
from fastapi import FastAPI, Form, Request, Response


server = (
    marimo.create_asgi_app()
    # Mount the dataframe app at /dataframes
    .with_app(path="/dataframes", root="../dataframe.py")
    # Mount the ansi app at /ansi
    .with_app(path="/ansi", root="../ansi.py")
    # Mount the buttons app at the root
    .with_app(path="", root="../buttons.py")
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


app.mount("/", server.build())

# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")
