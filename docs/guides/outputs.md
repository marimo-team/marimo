# Outputs

The last expression of a cell is its visual output, rendered above the cell.
Outputs are included in the "app" or read-only view of the notebook. marimo
comes out of the box a number of elements to help you make rich outputs,
documented in the [API reference](/api/index/).

<div align="center">
<figure>
<img src="/_static/outputs.gif"/>
</figure>
</div>

## Markdown

Markdown is written with the marimo library function [`mo.md`](/api/markdown/).
Writing markdown programmatically lets you make dynamic markdown: interpolate
Python values into markdown strings, conditionally render your markdown, and
embed markdown in other objects.

Here's a simple hello world example:

```python
import marimo as mo
```

```python
name = mo.ui.text(placeholder="Your name here")
mo.md(
  f"""
  Hi! What's your name?

  {name}
  """
)
```

```python
mo.md(
  f"""
  Hello, {name.value}!
  """
)
```

Notice that marimo knows how to render marimo objects in markdown: can just
embed them in [`mo.md()`](/api/markdown) using an f-string, and marimo will
figure out how to display them!

For other objects, like matplotlib plots, wrap
them in [`mo.as_html()`](#marimo.as_html) to tap into marimo's
media viewer:

```python
mo.md(
  f"""
  Here's a plot!

  {mo.as_html(figure)}
  """
)
```

```{admonition} Markdown editor
:class: tip

marimo can render cells that only use `mo.md()`, without an `f`-string, in a
markdown editor that supports common hotkeys.
```


## Layout

The marimo library also comes with elements for laying out outputs, including
[`mo.hstack`](#marimo.hstack), [`mo.vstack`](#marimo.vstack),
[`mo.accordion`](#marimo.accordion), [`mo.ui.tabs`](#marimo.ui.tabs), [`mo.sidebar`](#marimo.sidebar),
[`mo.nav_menu`](#marimo.nav_menu), [`mo.ui.table`](#marimo.ui.table),
and [many more](https://docs.marimo.io/api/layouts/index.html).

## Media

marimo comes with functions to display media, including images, audio,
video, pdfs, and more. See the [API docs](/api/media/index.md) for more info.
