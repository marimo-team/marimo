---
title: Markdown
marimo-version: 0.4.11
---

# Markdown file format

By default, marimo notebooks are stored as pure Python files. However,
you can also store and edit marimo notebooks as `.md` files, letting you
work on prose-heavy marimo notebooks in your editor of choice.

_Make sure to look at the markdown
[source code](https://github.com/marimo-team/marimo/blob/main/marimo/_tutorials/markdown_format.md)
of this tutorial!_
## Running markdown notebooks

To edit a markdown notebook, use

```bash
$ marimo edit notebook.md
```

To run it as an app, use

```bash
$ marimo run notebook.md
```
<!---->
## Exporting from Python

You can export marimo notebooks that are stored as Python to the markdown format
by running the following command:

```bash
$ marimo export md notebook.py > notebook.md
```
<!---->

## Creating Python cells

When you do need to create a Python cell in the markdown format, you can use a
special code block:

````md
```{.python.marimo}
import matplotlib.pyplot as plt
plt.plot([1, 2, 3, 4])
```
````

This will create the following cell:

```{.python.marimo}
import matplotlib.pyplot as plt
plt.plot([1, 2, 3, 4])
plt.gca()
```

As long as your code block contains the word `python` in a brace, like
`{python}`, or `{.python note="Whatever you want"}`, marimo will treat it as a
Python cell.
## `mo` tricks and tips

You can break up markdown into multiple cells by using an empty html tag `<!---->`:
<!---->
View the source of this notebook to see how this cell was created.
<!---->
You can still hide and disable code cells in markdown notebooks:

````md
```{python hide_code="true"}
import pandas as pd
pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
```
````

```{.python.marimo hide_code="true"}
import pandas as pd
pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
```

````md
```{python disabled="true"}
print("This code cell is disabled, there should be no output!")
```
````

```{.python.marimo disabled="true"}
print("This code cell is disabled, there should be no output!")
```

Additionally, marimo knows when your code has a syntax issue:

````md
```{python}
print("This code cell has a syntax error"
```
````

and on notebook save, will annotate the cell for you:

````md
```{python unparseable="true"}
print("This code cell has a syntax error"
```
````

```{.python.marimo unparsable="true"}
print("This code cell has a syntax error"
```

## Limitations of the markdown format

marimo's markdown support treats markdown as just plain old markdown. This
means that trying to use string interpolation (like this `f"{'🍃' * 7}"`) will
just give you the raw string. This lets you clearly delineate what values are
supposed to be computed, and what values are static. To interpolate Python
values, just use a Python cell:

```{.python.marimo}
'🍃' * 7
```

### Limitations on conversion

Whenever you try to implement a cell block like this:

````md
```{python}
mo.md("This is a markdown cell")
```
````

The markdown format will know to automatically keep this as markdown. However,
some ambiguous cases can't be converted to markdown like this:

````{.python.marimo}
mo.md("""
  This is a markdown cell with an execution block in it
  ```{python}
  # Too ambiguous to convert
  ```
  """)
````

It's not likely that you'll run into this issue, but rest assured that marimo
is working behind the scenes to keep your notebooks unambiguous and clean as
possible.
<!---->
### Naming cells

Since the markdown notebook really is just markdown, you can't import from a
markdown notebook cells like you can in a python notebook; but you can still
give your cells a name:

````md
```{.python.marimo name="maybe"}
# 🎵 Hey, I just met you, and this is crazy
```
````

```{.python.marimo name="maybe"}
# But here's my `cell_id`, so call me, `maybe` 🎶
```

## Converting back to the Python file format
The markdown format is supposed to lower the barrier for writing text heavy
documents, it's not meant to be a full replacement for the Python notebook
format. You can always convert back to a Python notebook if you need to:

```bash
$ marimo convert my_marimo.md > my_marimo.py
```

## More on markdown

Be sure to checkout the markdown.py tutorial (`marimo tutorial markdown`) for
more information on to type-set and render markdown in marimo.

```{.python.marimo hide_code="true"}
import marimo as mo
```
