# Richly display objects

marimo has built-in rich representations of many objects, including native
Python objects like lists and dicts as well as marimo objects like [UI
elements](/guides/interactivity.md) and libraries, including matplotlib,
seaborn, Plotly, altair pandas, and more. These rich representations are
displayed for the last expression of a cell, or when using
[`mo.output.append`](#marimo.output.append).

You can register rich displays with marimo for your own objects.

### Option 1: Implement a `_mime_` method

When displaying an object, marimo's media viewer checks for the presence of a
method called `_mime_`. This method should take no arguments and return
a tuple of two strings, the [mime type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types) and data to be displayed.

**Examples.**

```{eval-rst}
.. marimo-embed::
  :size: medium
  :mode: edit

  @app.cell(hide_code=True)
  def __():
    mo.md("**JSON**")

  @app.cell
  def __():
    import json

    class MyJSONObject(object):
        def __init__(self, data: dict[str, object]) -> None:
            self.data = data

        def _mime_(self) -> tuple[str, str]:
            return ("application/json", json.dumps(self.data))

    MyJSONObject({"hello": "world"})

  @app.cell(hide_code=True)
  def __():
    mo.md("**HTML**")

  @app.cell
  def __():
    class Colorize(object):
        def __init__(self, text: str) -> None:
            self.text = text

        def _mime_(self) -> tuple[str, str]:
            return (
              "text/html",
              "<span style='color:red'>" + self.text + "</span>",
            )

    Colorize("Hello!")

  @app.cell(hide_code=True)
  def __():
    mo.md("**Image**")

  @app.cell
  def __():
    class Image(object):
        def __init__(self, url: str) -> None:
            self.url = url

        def _mime_(self) -> tuple[str, str]:
            return ("image/png", self.url)

    Image("https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg")
```

### Option 2: Add a formatter to the marimo repo

When you don't have the ability to implement a `_mime_` method on the type
you want displayed, you can register custom formatters with marimo.

We welcome contributors to add formatters to the marimo codebase. [Look at our
codebase for
examples](https://github.com/marimo-team/marimo/tree/main/marimo/_output/formatters),
then open a pull request.

[AnyWidget](/api/inputs/anywidget.md)
