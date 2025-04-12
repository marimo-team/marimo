from __future__ import annotations

import modal
from modal import asgi_app

import marimo

server = marimo.create_asgi_app().with_app(path="", root="/marimo/notebook.py")

app = modal.App()


@app.function(
    image=modal.Image.debian_slim()
    .pip_install("marimo>=0.12.8", "fastapi")
    .add_local_dir("./nbs", remote_path="/marimo"),
    gpu=None,
    max_containers=1,
    memory=256,
)
@modal.concurrent(max_inputs=2)
@asgi_app()
def marimo_asgi():
    return server.build()
