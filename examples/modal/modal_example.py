from __future__ import annotations

import modal
from modal import asgi_app

import marimo

server = marimo.create_asgi_app().with_app(path="", root="/marimo/home.py")

app = modal.App()


@app.function(
    image=modal.Image.debian_slim().pip_install("marimo>=0.8.3", "fastapi"),
    gpu=False,
    concurrency_limit=1,
    allow_concurrent_inputs=2,
    memory=256,
    mounts=[modal.Mount.from_local_dir("./nbs", remote_path="/marimo")],
)
@asgi_app()
def marimo_asgi():
    return server.build()


if __name__ == "__main__":
    modal.serve(app)
