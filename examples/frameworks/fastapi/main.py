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
from typing import Callable, Coroutine
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import marimo
import os
import logging
from dotenv import load_dotenv
from fastapi import Form

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ui_dir = os.path.join(os.path.dirname(__file__), "..", "..", "ui")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

server = marimo.create_asgi_app()
app_names: list[str] = []

for filename in sorted(os.listdir(ui_dir)):
    if filename.endswith(".py"):
        app_name = os.path.splitext(filename)[0]
        app_path = os.path.join(ui_dir, filename)
        server = server.with_app(path=f"/{app_name}", root=app_path)
        app_names.append(app_name)

# Create a FastAPI app
app = FastAPI()

# Set up Jinja2 templates
templates = Jinja2Templates(directory=templates_dir)
# Simulated user database (replace with a real database in production)
users = {"admin": "password123"}


class LoginForm(BaseModel):
    username: str
    password: str


def get_current_user(request: Request):
    username = request.session.get("username")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return username


@app.middleware("http")
async def auth_middleware(
    request: Request,
    call_next: Callable[[Request], Coroutine[None, None, Response]],
) -> Response:
    if request.url.path == "/login":
        return await call_next(request)

    if "username" not in request.session:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    return await call_next(request)


@app.get("/login")
async def get_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    if username in users and password == users[username]:
        request.session["username"] = username
        logger.info(f"User {username} logged in successfully")
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    logger.warning(f"Failed login attempt for user {username}")
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Invalid credentials"}
    )


@app.get("/logout")
async def logout(request: Request):
    username = request.session.get("username")
    request.session.clear()
    logger.info(f"User {username} logged out")
    return RedirectResponse(url="/login")


@app.get("/")
async def home(request: Request, username: str = Depends(get_current_user)):
    return templates.TemplateResponse(
        "home.html", {"request": request, "username": username, "app_names": app_names}
    )


@app.get("/ping")
async def root():
    return {"message": "pong"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error occurred: {exc.detail}")
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "detail": exc.detail},
        status_code=exc.status_code,
    )


app.mount("/", server.build())

# Add session middleware
app.add_middleware(
    SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "your-secret-key")
)

# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")
