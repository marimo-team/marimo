# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "shiny",
#     "marimo",
#     "vega-datasets==0.9.0",
# ]
# ///
from shiny import App, render, ui
from htmltools import HTML
import marimo
import os
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import RedirectResponse


ui_dir = os.path.join(os.path.dirname(__file__), "..", "..", "ui")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

marimo_app = marimo.create_asgi_app()
app_names: list[str] = []

for filename in sorted(os.listdir(ui_dir)):
    if filename.endswith(".py"):
        app_name = os.path.splitext(filename)[0]
        app_path = os.path.join(ui_dir, filename)
        marimo_app = marimo_app.with_app(path=f"/{app_name}", root=app_path)
        app_names.append(app_name)

shiny_ui = ui.page_fluid(
    ui.head_content(
        ui.tags.script(src="https://cdn.tailwindcss.com"),
        ui.tags.link(
            href="https://cdn.jsdelivr.net/npm/daisyui@4.11.1/dist/full.min.css",
            rel="stylesheet",
        ),
    ),
    ui.output_ui("_html"),
    title="Marimo apps in Shiny",
)


def shiny_server(input, output, session):
    @render.ui
    def _html():
        subdiv = []
        for name in app_names:
            subdiv.append(
                f"""
            <div class="bg-base-200 rounded-lg shadow-md hover:shadow-xl 
                transition-shadow duration-300 w-64">
              <a href="/{name}" target="_blank" class="block w-full h-full">
                <div class="p-4">
                  <h2 class="text-xl text-gray-300 mb-2" style"font: white" >{name}</h2>
                  <p class="text-sm text-gray-500">Click to open app</p>
                </div>
              </a>
            </div>
                """
            )
        body = f"""
<div class="min-h-screen bg-gradient-to-br from-base-200 to-base-300 p-8">
    <div class="container mx-auto px-4 py-16 bg-base-100 rounded-box shadow-xl">
        <h1 class="text-4xl text-blue-500 font-bold mb-8 text-center">Marimo dashboard in Shiny</h1>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {''.join(subdiv)}
        </div>
    </div>
</div>
        """
        return HTML(body)


app = App(shiny_ui, shiny_server)


wsgi_app = WSGIMiddleware(app)

# Create the final ASGI app
asgi_app = Starlette(
    routes=[
        Route("/", endpoint=lambda request: RedirectResponse(url="/shiny/")),
        Mount("/shiny", app=wsgi_app),
        Mount("/", app=marimo_app.build()),
    ]
)
