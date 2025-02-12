# FastAPI + marimo, as an API endpoint

This is a simple example of how to use FastAPI with marimo. This example turns marimo notebooks into an API endpoint, which can be embedded in any FastAPI app.

- Turning functions defined in a notebook into an API endpoint
- Overriding global variables and returning cell outputs

## Running the app

1. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
2. Run the app with `uv run --no-project main.py`
3. Then run `curl http://localhost:8000/greet?name=coder`
