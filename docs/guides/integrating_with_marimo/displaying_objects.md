# Richly display objects

marimo has built-in rich representations of many objects, including native
Python objects like lists and dicts as well as marimo objects like [UI
elements](../interactivity.md) and libraries, including matplotlib,
seaborn, Plotly, altair pandas, and more. These rich representations are
displayed for the last expression of a cell, or when using
[`mo.output.append`][marimo.output.append].

You can register rich displays with marimo for your own objects. You have
three options:

1. Implement a `_display_()` method
2. Implement a `_mime_()` method
3. Implement an IPython-style `_repr_*_()` method

If you can't modify the object, you can also add a formatter to the marimo library (option 4).

The return value of these methods determines what is shown. `_display_`
has the highest precedence, then built-in formatters, then `_mime_`, then `IPython` style `_repr_*_`
methods.

## Option 1: Implement a `_display_()` method

If an object implements a `_display_()`, marimo will use its return value
to visualize the object as an output.

For example:

```python
class Dice:
    def _display_(self):
        import random

        return f"You rolled {random.randint(0, 7)}"
```

The return value of `_display_` can be any Python object, for example a
a matplotlib plot, a dataframe, a list, `mo.Html`, or a `mo.ui` element, and
marimo will attempt to display it.

In addition to being the most convenient way do define a custom display in
marimo (in terms of syntax), it is also helpful for library developers: this
option lets you make an object showable in marimo without adding marimo as a
dependency to your project.

However, if you need to display an object that marimo does not know how to
render (for example, maybe you are building a new plotting library), then
you need to consider of the other options below.

## Option 2: Implement an IPython `_repr_*_()` method

marimo can render objects that implement
[IPython's `_repr_*_()` protocol](https://ipython.readthedocs.io/en/stable/config/integrating.html#custom-methods)
for rich display. Here is an example of implementing `_repr_html_`, borrowed
from IPython's documentation:

```python
class Shout:
    def __init__(self, text):
        self.text = text

    def _repr_html_(self):
        return "<h1>" + self.text + "</h1>"
```

We support the following methods:

- `_repr_html_`
- `_repr_mimebundle_`
- `_repr_svg_`
- `_repr_json_`
- `_repr_png_`
- `_repr_jpeg_`
- `_repr_markdown_`
- `_repr_latex_`
- `_repr_text_`

**Note:** marimo currently does not handle any optional metadata returned by `_repr_mimebundle_`.

## Option 3: Implement a `_mime_` method

When displaying an object, marimo's media viewer checks for the presence of a
method called `_mime_`. This method should take no arguments and return
a tuple of two strings, the [mime type](https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types) and data to be displayed as a string.

**Examples.**

/// marimo-embed
    size: medium
    mode: edit

```python
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

///

## Option 4: Add a formatter to the marimo repo

The recommended way to render rich displays of objects in marimo is to
implement `_display_` if possible, otherwise either the IPython `_repr_*_()_`
protocol or marimo's `_mime_()` protocol. If you are a a user of a library that
does not render properly in marimo, consider asking the library maintainers to
implement one of these protocols.

If it is not possible to implement a renderer protocol on the type
you want displayed, we will consider contributions to add formatters to the
marimo codebase. [Look at our codebase for
examples](https://github.com/marimo-team/marimo/tree/main/marimo/_output/formatters),
then open a pull request.
