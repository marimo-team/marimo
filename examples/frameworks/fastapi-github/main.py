# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi",
#     "marimo",
#     "starlette",
#     "requests",
#     "pydantic",
#     "jinja2",
#     "vega-datasets==0.9.0",
# ]
# ///
import tempfile
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
import marimo
import os
import logging
import requests
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
GITHUB_REPO = os.environ.get("GITHUB_REPO", "marimo-team/marimo")
ROOT_DIR = os.environ.get("ROOT_DIR", "examples/ui")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

# Set up templates
templates = Jinja2Templates(directory=templates_dir)


def download_github_files(repo: str, path: str = "") -> list[tuple[str, str]]:
    """Download files from GitHub repo, returns list of (file_path, content)"""
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    response = requests.get(api_url)
    response.raise_for_status()

    files: list[tuple[str, str]] = []
    for item in response.json():
        print(item)
        if item["type"] == "file" and item["name"].endswith(".py"):
            content_response = requests.get(item["download_url"])
            files.append(
                (os.path.join(path, item["name"]), content_response.text)
            )
        elif item["type"] == "dir":
            files.extend(
                download_github_files(repo, os.path.join(path, item["name"]))
            )
    return files


tmp_dir = tempfile.TemporaryDirectory()


def setup_apps():
    """Download and setup marimo apps from GitHub"""
    files = download_github_files(GITHUB_REPO, ROOT_DIR)
    server = marimo.create_asgi_app()
    app_names: list[str] = []

    for file_path, content in files:
        app_name = Path(file_path).stem
        local_path = Path(tmp_dir.name) / file_path

        # Create directories if they don't exist
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file content
        local_path.write_text(content)

        # Add to marimo server
        server = server.with_app(path=f"/{app_name}", root=str(local_path))
        app_names.append(app_name)
        logger.info(f"Added app: {app_name} from {file_path}")

    return server, app_names


# Create a FastAPI app
app = FastAPI()

# Setup marimo apps
server, app_names = setup_apps()


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html", {"request": request, "app_names": app_names}
    )


@app.get("/ping")
async def root():
    return {"message": "pong"}


# Mount the marimo server
app.mount("/", server.build())

# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")
