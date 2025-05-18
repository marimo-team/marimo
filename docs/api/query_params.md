# Query Parameters

Query parameters are key-value pairs appended to the end of a URL to pass data to the server or customize a request. 

Use `mo.query_params` to access query parameters passed to the notebook. You
can also use `mo.query_params` to set query parameters in order to keep track
of state in the URL. This is useful for bookmarking or sharing a particular
state of the notebook while running as an application with `marimo run`.

::: marimo.query_params

## Pydantic Models for Query Parameters

One of the use cases for URL query parameters is to set the initial state of UI elements.

Passing query parameters into a Pydantic model helps document and validate the parameters.


```python
import marimo as mo
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    r: int = Field(28, ge=0, le=255, description="Red Channel")
    g: int = Field(115, ge=0, le=255, description="Green Channel")
    b: int = Field(97, ge=0, le=255, description="Blue Channel")
    message: str = Field("<br>", description="Some text")

model = MyModel(**mo.query_params().to_dict())

# UI with initial state from query params
r_slider = mo.ui.slider(start=0, stop=255, step=1, label="R", value=model.r)
g_slider = mo.ui.slider(start=0, stop=255, step=1, label="G", value=model.g)
b_slider = mo.ui.slider(start=0, stop=255, step=1, label="B", value=model.b)
```

In the next cell: (see [live](https://marimo.app/l/03egkc?g=255))
```python
bg_color = f"rgb({r_slider.value},{g_slider.value},{b_slider.value})"
mo.vstack([
    r_slider, g_slider, b_slider,
    mo.Html(model.message + bg_color).style(background_color=bg_color, text_align="center")
])
```

When using [marimo apps mounted to FastAPI](../guides/deploying/programmatically.md), the Pydantic model can be passed into the API documentation for the main app.

!!! note "CLI arguments"

    You can also access command-line arguments passed to the notebook using
    `mo.cli_args`. This allows you to pass arguments to the notebook that are not controllable by the user.
