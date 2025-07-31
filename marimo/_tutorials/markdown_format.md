---
title: Markdown
marimo-version: 0.13.2
author: Marimo Team
description: >-
  Markdown is a lightweight markup language with plain text formatting syntax. `marimo`
  notebooks can be stored as markdown files, allowing you to work on prose-heavy notebooks
  in your editor of choice.
pyproject: |-
  requires-python = ">=3.12"
  dependencies = [
      "marimo",
      "duckdb==1.2.2",
      "matplotlib==3.10.1",
      "sqlglot==26.16.2",
  ]
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
```python {.marimo}
import matplotlib.pyplot as plt
plt.plot([1, 2, 3, 4])
```
````

This will create the following cell:

```python {.marimo}
import matplotlib.pyplot as plt

plt.plot([1, 2, 3, 4])
plt.gca()
```

As long as your code block contains the word `marimo` in a brace, like
`{marimo}`, or `{.marimo note="Whatever you want"}`, marimo will treat it as a Python cell.

## `mo` tricks and tips

You can break up markdown into multiple cells by using an empty html tag `<!---->`:
<!---->
View the source of this notebook to see how this cell was created.
<!---->
You can still hide cell code in markdown notebooks:

````md
```python {.marimo hide_code="true"}
form = (
    # ...
    # Just something a bit more complicated
    # you might not want to see in the editor.
    # ...
)
form
```
````

```python {.marimo hide_code="true"}
form = (
    mo.md('''
    **Just how great is markdown?.**

    {markdown_is_awesome}

    {marimo_is_amazing}
''')
    .batch(
        markdown_is_awesome=mo.ui.text(label="How much do you like markdown?", placeholder="It is pretty swell 🌊"),
        marimo_is_amazing=mo.ui.slider(label="How much do you like marimo?", start=0, stop=11, value=11),
    )
    .form(show_clear_button=True, bordered=False)
)
form
```

and disable cells too:

````md
```python {.marimo disabled="true"}
print("This code cell is disabled, there should be no output!")
```
````

```python {.marimo disabled="true"}
print("This code cell is disabled, there should be no output!")
```

Additionally, marimo knows when your code has a syntax issue:

````md
```python {.marimo}
print("This code cell has a syntax error"
```
````

and on notebook save, will annotate the cell for you:

````md
```python {.marimo unparseable="true"}
print("This code cell has a syntax error"
```
````

```python {.marimo unparsable="true"}
print("This code cell has a syntax error"
```

## Limitations of the markdown format

marimo's markdown support treats markdown as just plain old markdown. This
means that trying to use string interpolation (like this `f"{'🍃' * 7}"`) will
just give you the raw string. This lets you clearly delineate what values are
supposed to be computed, and what values are static. To interpolate Python
values, just use a Python cell:

```python {.marimo}
mo.md(f"""Like so: {"🍃" * 7}""")
```

### Limitations on conversion

Whenever you try to implement a cell block like this:

````md
```python {.marimo}
mo.md("This is a markdown cell")
```
````

The markdown format will know to automatically keep this as markdown. However,
some ambiguous cases can't be converted to markdown like this:

````python {.marimo}
mo.md(
    """
    This is a markdown cell with an execution block in it
    ```python {.marimo}
    # Too ambiguous to convert
    ```
    """
)
````

It's not likely that you'll run into this issue, but rest assured that marimo
is working behind the scenes to keep your notebooks unambiguous and clean as
possible.
<!---->
### Saving multicolumn mode

Multicolumn mode works, but the first cell in a column must be a python cell in
order to specify column start and to save correctly:

````md
```python {.marimo column="1"}
print("First cell in column 1")
```
````
<!---->
### Naming cells

Since the markdown notebook really is just markdown, you can't import from a
markdown notebook cells like you can in a python notebook; but you can still
give your cells a name:

````md
```python {.marimo name="maybe"}
# 🎵 Hey, I just met you, and this is crazy
```
````

```python {.marimo name="maybe"}
# But here's my `cell_id`, so call me, `maybe` 🎶
```

### SQL in markdown

You can also run SQL queries in markdown cells through marimo, using a `sql` code block. For instance:

````md
```sql {.marimo}
SELECT GREATEST(x, y), SQRT(z) from uniformly_random_numbers
```
````

The resultant distribution may be surprising! 🎲[^surprise]

[^surprise]: The general distributions should be the same

```sql {.marimo}
SELECT GREATEST(a, b), SQRT(c) from uniformly_random_numbers
```

In this SQL format, Python variable interpolation in SQL queries occurs automatically. Additionally, query results can be assigned to a dataframe with the `query` attribute.
For instance, here's how to create a random uniform distribution and assign it to the dataframe `uniformly_random_numbers` used above:

````md
```sql {.marimo query="uniformly_random_numbers" hide_output="true"}
SELECT i.range::text AS id,
       random() AS x,
       random() AS y,
       random() AS z
FROM
    -- Note sample_count comes from the slider below!
    range(1, {sample_count.value + 1}) i;
```
````

You can learn more about other SQL use in the SQL tutorial (`marimo tutorial sql`)

```python {.marimo hide_code="true"}
sample_count = mo.ui.slider(1, 1000, value=1000, label="Sample Count")
sample_count
```

```sql {.marimo query="uniformly_random_numbers" hide_output="True"}
SELECT i.range::text AS id,
       random() AS a,
       random() AS b,
       random() AS c
FROM range(1, {sample_count.value + 1}) i;
```

## Converting back to the Python file format

The markdown format is supposed to lower the barrier for writing text heavy
documents, it's not meant to be a full replacement for the Python notebook
format. You can always convert back to a Python notebook if you need to:

```bash
$ marimo convert my_marimo.md > my_marimo.py
```
<!---->
## More on markdown

Be sure to checkout the markdown.py tutorial (`marimo tutorial markdown`) for
more information on to type-set and render markdown in marimo.

```python {.marimo hide_code="true"}
import marimo as mo
```
