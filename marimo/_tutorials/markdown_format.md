---
title: Markdown
marimo-version: 0.4.11
---

# marimo in Markdown!

Everything in marimo is pure Python, but sometimes, annotating your notebook
in markdown can be a little cumbersome.
<!---->
For example, here's the code that rendered the above title and
paragraph:

````md
```{python}
mo.md(
    '''
    # marimo in Markdown!

    Everything in marimo is pure Python, but sometimes, annotating your notebook
    in markdown can be a little cumbersome.
    '''
)
```
````

with markdown notebook support for marimo, you can write and save markdown
directly, and marimo will execute the necessary Python code for you behind the
scenes. This allows you to focus on prose, and not formatting your text in a block
string.
<!---->
## Python cells in markdown

When you do need to create a Python cell in the markdown format, you can use a
special code block:

````md
```{python}
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
<!---->
## Exporting from Python

Do you have a notebook that you think might better be suited for a markdown notebook?
You can export your notebook to markdown by running the following code:

```bash
$ marimo export md my_marimo.py > my_marimo.md
```

by default, marimo will extract your markdown cells, and wrap your Python cells
in `{.python.marimo}` code blocks. Although `{python}` might be more concise,
this format is chosen such that code highlighting will work in your favourite
IDE.
<!---->
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
just give you the raw string. This is a benefit, as you can clearly delineate
what values are supposed to be computed, and what values are static;

and there's nothing stopping you from executing python to achieve the same effect,

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
  # To ambiguous to convert
  ```
  """)
````

It's not likely that you'll run into this issue, but rest assured that marimo
is working behind the scenes to keep your notebooks unambiguous and clean as
possible.
<!---->
### More limitations

Since the markdown notebook really is just markdown, you can't import from a
markdown notebook cells like you can in a python notebook; but you can still
give your cells a name:

````md
```{python name="maybe"}
# 🎵 Hey, I just met you, and this is crazy
```
````

```{.python.marimo name="maybe"}
# But here's my `cell_id`, so call me, `maybe` 🎶
```

you can even run a notebook:

```bash
$ marimo run my_marimo.md
```

the markdown format is supposed to lower the barrier for writing text heavy
documents, it's not meant to be a full replacement for the python notebook
format. You can always convert back to a python notebook if you need to:

```bash
$ marimo convert my_marimo.md > my_marimo.py
```
<!---->
## More?!

Be sure to checkout the markdown.py tutorial for more information on to type-set
and render markdown in marimo.

```{.python.marimo hide_code="true"}
import marimo as mo
```
