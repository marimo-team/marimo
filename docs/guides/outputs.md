# Visualizing outputs

The last expression of a cell is its visual output, rendered above the cell.
Outputs are included in the "app" or read-only view of the notebook. marimo
comes out of the box a number of elements to help you make rich outputs,
documented in the [API reference](../api/index.md).

<div align="center">
<figure>
<video autoplay muted loop width="100%" height="100%" align="center" src="/_static/outputs.webm">
</video>
</figure>
</div>

## Markdown

Markdown is written with the marimo library function [`mo.md`][marimo.md].
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

Notice that marimo knows how to render marimo objects in markdown: you can just
embed them in [`mo.md()`][marimo.md] using an f-string, and marimo will
figure out how to display them!

For other objects, like matplotlib plots, wrap
them in [`mo.as_html()`][marimo.as_html] to tap into marimo's
media viewer:

```python
mo.md(
  f"""
  Here's a plot!

  {mo.as_html(figure)}
  """
)
```

### Markdown editor

marimo automatically renders cells that only use `mo.md("")`, without an
`f`-string, in a markdown editor that supports common hotkeys.

Because the Markdown editor doesn't support f-strings, you'll need to use
`mo.md` directly to interpolate Python values into your Markdown. You can
switch between the Markdown and Python editors by clicking the button in the
top right.

<div align="center">
<figure>
<video autoplay muted loop width="100%" height="100%" align="center" src="/_static/docs-markdown-toggle.webm">
</video>
<figcaption>marimo is pure Python, even when you're using markdown.</figcaption>
</figure>
</div>

## Layout

The marimo library also comes with elements for laying out outputs, including
[`mo.hstack`][marimo.hstack], [`mo.vstack`][marimo.vstack],
[`mo.accordion`][marimo.accordion], [`mo.ui.tabs`][marimo.ui.tabs], [`mo.sidebar`][marimo.sidebar],
[`mo.nav_menu`][marimo.nav_menu], [`mo.ui.table`][marimo.ui.table],
and [many more](../api/layouts/index.md).

## Progress bars

Use [`mo.status.progress_bar`][marimo.status.progress_bar] and
[`mo.status.spinner`][marimo.status.spinner] to create progress indicators:

```python
# mo.status.progress_bar is similar to TQDM
for i in mo.status.progress_bar(range(10)):
  print(i)

```

## Media

marimo comes with functions to display media, including images, audio,
video, pdfs, and more. See the [API docs](../api/media/index.md) for more info.

## Imperatively adding outputs

While a cell's output is its last expression, it can at times be helpful
to imperatively add to the output area while a cell is running. marimo
provides utility functions like
[`mo.output.append`][marimo.output.append] for accomplishing this; see the
[API docs](../api/outputs.md) for more information.

## Console Outputs

Console outputs, such as print statements, show up below a cell in the console
output area; they are not included in the output area or app view by default.

To include console outputs in the cell output area, use
[`mo.redirect_stdout`][marimo.redirect_stdout] or
[`mo.redirect_stderr`][marimo.redirect_stderr]:

```python
with mo.redirect_stdout():
  print("Hello, world!")
```

marimo also includes utility functions for [capturing standard out][marimo.capture_stdout] and [standard error][marimo.capture_stderr] without redirecting them. See the [API docs](../api/outputs.md#console-outputs) for more.

## Threading

To create a thread that can reliably communicate outputs to the frontend,
use [`mo.Thread`][marimo.Thread], which has exactly the same API as
as `threading.Thread`.

If you need to forward outputs from threads spawned by third-party code, try
patching `threading.Thread`:

```python
import threading
import marimo as mo

threading.Thread = mo.Thread
```
