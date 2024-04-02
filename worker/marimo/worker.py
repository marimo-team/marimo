# from fastapi import FastAPI, Request
# from pydantic import BaseModel


# async def on_fetch(request, env):
#     import asgi

#     return await asgi.fetch(app, request, env)


# app = FastAPI()


# @app.get("/")
# async def root():
#     return {"message": "Hello, World!"}


# @app.get("/env")
# async def root(req: Request):
#     env = req.scope["env"]
#     return {
#         "message": "Here is an example of getting an environment variable: "
#         + env.MESSAGE
#     }


# class Item(BaseModel):
#     name: str
#     description: str | None = None
#     price: float
#     tax: float | None = None


# @app.post("/items/")
# async def create_item(item: Item):
#     return item


# @app.put("/items/{item_id}")
# async def create_item(item_id: int, item: Item, q: str | None = None):
#     result = {"item_id": item_id, **item.dict()}
#     if q:
#         result.update({"q": q})
#     return result


# @app.get("/items/{item_id}")
# async def read_item(item_id: int):
#     return {"item_id": item_id}


import micropip
from fastapi import FastAPI

from marimo._server.asgi import create_asgi_app

DEPS = [
    "docutils",
    "Pygments",
    "jedi",
    "pyodide-http",
    "markdown",
    "pymdown-extensions",
]
installed = False


async def on_fetch(request, env):
    import asgi

    global installed
    if not installed:
        print("Installing dependencies")
        await micropip.install(DEPS)

        # Create a marimo asgi app
        print("Creating marimo app")
        server = create_asgi_app().with_app(path="", root="./wasm-intro.py")
        app.mount("/", server.build())
        # session, bridge = marimo.create_session(
        #     filename="\${t}",
        #     query_params={},
        #     message_callback=lambda msg: print(msg),
        # )
        installed = True
        print("Dependencies installed")

    return await asgi.fetch(app, request, env)


app = FastAPI()
