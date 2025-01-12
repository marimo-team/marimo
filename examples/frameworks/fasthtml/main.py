# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "python-fasthtml",
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///
from fasthtml.common import *
import marimo
import os

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


# Loading tailwind and daisyui
headers = (
    Script(src="https://cdn.tailwindcss.com"),
    Link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/daisyui@4.11.1/dist/full.min.css")
)


app = FastHTML()

@app.get("/")
def home():
    return (
        *headers,
        Title("marimo apps"),
        Main(
            Div(
                H1("marimo dashboard", cls="text-4xl font-bold mb-8 text-center"),
                Div(
                    *[
                        Div(
                            A(
                                Div(
                                    H2(app_name, cls="text-xl font-semibold mb-2"),
                                    P("Click to open app", cls="text-sm text-gray-500"),
                                    cls="p-4"
                                ),
                                href=f"/{app_name}",
                                target="_blank",
                                cls="block w-full h-full"
                            ),
                            cls="bg-base-200 rounded-lg shadow-md hover:shadow-xl transition-shadow duration-300 w-64"
                        ) for app_name in app_names
                    ],
                    cls="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6"
                ),
                cls="container mx-auto px-4 py-16 bg-base-100 rounded-box shadow-xl"
            ),
            cls="min-h-screen bg-gradient-to-br from-base-200 to-base-300 p-8"
        )
    )

app.mount("/", server.build())

if __name__ == "__main__":
    serve()
