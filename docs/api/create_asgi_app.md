---
description: "API reference for marimo.create_asgi_app — build ASGI apps that serve notebooks in run mode."
---

# create_asgi_app

Build an ASGI application that serves one or more marimo notebooks in **run**
mode. This is the public embedding/deploy surface for integrating marimo with
FastAPI, Starlette, uvicorn, or other ASGI stacks.

For walkthroughs (auth, dynamic directories, mounting), see
[Programmatic usage](../guides/deploying/programmatically.md).

!!! note

    Autodoc via `::: marimo.create_asgi_app` may fail in the public docs build
    because the implementation lives under the private package
    `marimo._server.asgi`, which mkdocstrings filters out (`!^_`). Signature and
    notes below match the public re-export on `marimo.create_asgi_app`.

## Signature

```python
def create_asgi_app(
    *,
    quiet: bool = False,
    include_code: bool = False,
    token: str | None = None,
    skew_protection: bool = False,
    session_ttl: int = 120,
    asset_url: str | None = None,
    redirect_console_to_browser: bool = False,
    show_tracebacks: bool = False,
    html_head: str | None = None,
    execute_opengraph_generators: bool = False,
) -> ASGIAppBuilder: ...
```

| Parameter | Default | Notes |
| --- | --- | --- |
| `quiet` | `False` | Suppress standard output from the server |
| `include_code` | `False` | Expose notebook source in the served app |
| `token` | `None` | Auth token; empty token when omitted |
| `skew_protection` | `False` | Prompt clients to reload after server upgrades |
| `session_ttl` | `120` | Session TTL in seconds |
| `asset_url` | `None` | CDN/static asset base; may include `{version}` |
| `redirect_console_to_browser` | `False` | Stream stdout/stderr to the browser UI |
| `show_tracebacks` | `False` | Toast + modal for full Python tracebacks |
| `html_head` | `None` | Global HTML injected into every notebook `<head>` |
| `execute_opengraph_generators` | `False` | Run notebook OG generators (trusted dirs only) |

Returns an **`ASGIAppBuilder`**. Chain `.with_app(...)` / `.with_dynamic_directory(...)`, then `.build()`.

## Minimal example

```python
import uvicorn
from marimo import create_asgi_app

app = (
    create_asgi_app()
    .with_app(path="/", root="home.py")
    .with_app(path="/dashboard", root="dashboard.py")
    .build()
)

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
```

## FastAPI mount

```python
from fastapi import FastAPI
from marimo import create_asgi_app

api = FastAPI()
notebooks = create_asgi_app().with_app(path="/app", root="app.py").build()
api.mount("/", notebooks)
```

## Related

- [Deploying programmatically](../guides/deploying/programmatically.md)
- [Authentication](../guides/deploying/authentication.md)
- [Open Graph metadata](../guides/publishing/opengraph.md)
