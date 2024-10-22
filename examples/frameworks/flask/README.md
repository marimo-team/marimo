# Flask + marimo

This is a simple example of how to use Flask with marimo. This example programmatically creates multiple marimo apps from a directory, and then serves them as a single Flask app.

This example includes:

- Authentication
- Serving multiple marimo apps from a directory
- A home page listing all the apps
- Loading environment variables from a `.env` file
- Basic logging

## Running the app

1. [Install `uv`](https://github.com/astral-sh/uv/?tab=readme-ov-file#installation)
2. Run the app with `uv run --no-project main.py`

This will start the Flask development server.
