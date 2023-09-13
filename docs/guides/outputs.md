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

## Output layouts

By default outputs are rendered in a vertical layout, but you can also use
a **Grid layout** to arrange outputs in a 12 column grid. Different layouts each have their
our layout schema that gets saved to disk. Cells can be arranged within the layout
regardless of their order in the notebook or dependencies between them.

<div align="center">
<figure>
<img src="/_static/outputs-grid.gif"/>
</figure>
</div>
