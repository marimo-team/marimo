---
description: "API reference for marimo.create_asgi_app — build ASGI apps that serve notebooks in run mode."
---

# create_asgi_app

Build an ASGI application that serves one or more marimo notebooks in **run**
mode. This is the public embedding / deploy surface for FastAPI, Starlette,
uvicorn, and related stacks.

Walkthroughs (auth, dynamic directories, mounting) live in
[Programmatic usage](../guides/deploying/programmatically.md).

::: marimo.create_asgi_app
    options:
      # Implementation lives in marimo._server.asgi; allow underscored modules
      # for this page so the public re-export can resolve for mkdocstrings.
      filters: []
      show_root_heading: true
      show_source: false
      members: false

## ASGIAppBuilder

Builder returned by [`create_asgi_app`][marimo.create_asgi_app]. Chain
`with_app` / `with_dynamic_directory`, then call `build()`.

::: marimo._server.asgi.ASGIAppBuilder
    options:
      filters: []
      show_root_heading: true
      show_source: false
      members:
        - with_app
        - with_dynamic_directory
        - build
