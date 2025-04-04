# Coming from Jupyter

If you're coming from Jupyter, here are a few tips to help you adapt to marimo
notebooks.

## How marimo runs cells

The biggest difference between marimo and Jupyter is the [execution model](../reactivity.md).

A **Jupyter** notebook is a **REPL**: you execute blocks of code one at a time,
and Jupyter has no understanding of how different blocks are related to each
other. As a result a Jupyter notebook can easily
accumulate **"hidden state"** (and hidden bugs) --- you might accidentally execute
cells out of order, or you might run (or delete) a cell but forget to re-run
cells that depended on its variables. Because of this, Jupyter notebooks
suffer from a [reproducibility crisis](../../faq.md#faq-problems), with over
a third of Jupyter notebooks on GitHub failing to reproduce.

Unlike Jupyter, **marimo** notebooks understand how different blocks of
code are related to each other, modeling your code as a graph on cells
based on variable declarations and references. This eliminates hidden
state, and it's also what enables marimo notebooks to be reused as
apps and scripts.

**By default, if you run a cell in marimo, all other cells that read its
variables run automatically.** While this ensures that your code and outputs are
in sync, it can take some time getting used to. **Here are some tips and tools to
help you adapt to marimo's execution model.**

### Configure marimo's runtime

[Configure marimo's runtime](../configuration/runtime_configuration.md) to
not autorun on startup or on cell execution.

Even when autorun is disabled, marimo still tracks dependencies across cells,
marking dependents of a cell as stale when you run it. You can click a single
button to run all your stale cells and bring your notebook back up-to-date.

### Stop execution with `mo.stop`

Use [`mo.stop`][marimo.stop] to stop a cell from executing if a condition
is met:

```python
# if condition is True, the cell will stop executing after mo.stop() returns
mo.stop(condition)
# this won't be called if condition is True
expensive_function_call()
```

Use [`mo.stop()`][marimo.stop] in conjunction with
[`mo.ui.run_button()`][marimo.ui.run_button] to require a button press for
expensive cells:

/// marimo-embed
    size: medium

```python
@app.cell
def __():
    run_button = mo.ui.run_button()
    run_button
    return

@app.cell
def __():
    mo.stop(not run_button.value, mo.md("Click 👆 to run this cell"))
    mo.md("You clicked the button! 🎉")
    return
```

///

### Working with expensive notebooks

For more tips on adapting to marimo's execution model, see our guide
on [working with expensive notebooks](../expensive_notebooks.md).

## Redefining variables

marimo "compiles" your notebook cells into a directed graph on cells,
linked by variable declarations and references, reusing this graph to
run your notebook as a script or app. For marimo's compilation to work,
the same variable cannot be defined in multiple cells; otherwise, marimo
wouldn't know what order to run cells in.

To adapt to the restriction, we suggest:

1. Encapsulating code into functions when possible, to minimize the number
   of global variables.
2. Prefixing temporary variables with an underscore (`_my_temporary`), which
   makes the variable **local** to a cell.
3. Mutating variables in the cell that defines them.

When working with **dataframes**, you might be used to redefining the same `df`
variable in multiple cells. That won't work in marimo. Instead, try merging
the cells into a single cell:

_Don't_ do this:

```python
df = pd.DataFrame({"my_column": [1, 2]})
```

```python
df["another_column"] = [3, 4]
```

_Instead_, do this:

```python
df = pd.DataFrame({"my_column": [1, 2]})
df["another_column"] = [3, 4]
```

If you do need to transform a dataframe across multiple cells, you can
alias the dataframe:

```python
df = pd.DataFrame({"my_column": [1, 2]})
```

```python
augmented_df = df
augmented_df["another_column"] = [3, 4]
```

## marimo's file format

marimo stores notebooks as Python, not JSON. This lets you version notebooks
with git, [execute them as scripts](../scripts.md), and import named
cells into other Python files. However, it does mean that your notebook outputs
(e.g., plots) are not stored in the file.

If you'd like to keep a visual record of your notebook work, [enable
the "Auto-download as HTML/IPYNB" setting](../configuration/index.md), which will
periodically snapshot your notebook as HTML or IPYNB to a `__marimo__` folder in the
notebook directory.

### Converting Jupyter notebooks to marimo notebooks

Convert Jupyter notebooks to marimo notebooks at the command-line:

```bash
marimo convert your_notebook.ipynb -o your_notebook.py
```

### Exporting marimo notebooks to Jupyter notebooks

Export to an `ipynb` file with

```bash
marimo export ipynb notebook.py -o notebook.ipynb
```

Note that some marimo library functions, including UI elements,
won't work in Jupyter notebooks.

## Magic commands

Because marimo notebooks are just Python (improving maintainability), marimo
doesn't support IPython magic commands or `!`-prefixed console commands. Here
are some alternatives.

### Run console commands with subprocess.run

To run a console command, use Python's [subprocess.run](https://docs.python.org/3/library/subprocess.html#subprocess.run):

```python
import subprocess

# run: "ls -l"
subprocess.run(["ls", "-l"])
```

### Common magic commands replacements

| Magic Command | Replacement                                                                                    |
| ------------- | ---------------------------------------------------------------------------------------------- |
| %cd           | `os.chdir()`, see also [`mo.notebook_dir()`][marimo.notebook_dir]                              |
| %clear        | Right-click or toggle the cell actions                                                         |
| %debug        | Python's built-in debugger: `breakpoint()`                                                     |
| %env          | `os.environ`                                                                                   |
| %load         | N/A - use Python imports                                                                       |
| %load_ext     | N/A                                                                                            |
| %autoreload   | marimo's [module autoreloader](../editor_features/module_autoreloading.md)                     |
| %matplotlib   | marimo auto-displays plots                                                                     |
| %pwd          | `os.getcwd()`                                                                                  |
| %pip          | Use marimo's [built-in package management](../editor_features/package_management.md)           |
| %who_ls       | `dir()`, `globals()`, [`mo.refs()`][marimo.refs], [`mo.defs()`][marimo.defs]                   |
| %system       | `subprocess.run()`                                                                             |
| %%time        | `time.perf_counter()` or Python's timeit module                                                |
| %%timeit      | Python's timeit module                                                                         |
| %%writefile   | `with open("file.txt", "w") as f: f.write()`                                                   |
| %%capture     | [`mo.capture_stdout()`][marimo.capture_stdout], [`mo.capture_stderr()`][marimo.capture_stderr] |
| %%html        | [`mo.Html()`][marimo.Html] or [`mo.md()`][marimo.md]                                           |
| %%latex       | [`mo.md(r'$$...$$')`][marimo.md]                                                               |

### Installing packages with marimo's package manager

Use marimo's package management sidebar panel to install packages to your current
environment. Learn more in our [package management
guide](../editor_features/package_management.md).

## Interactive guide

This guide contains additional tips to help you adapt to marimo. Fun fact: the
guide is itself a marimo notebook!

<iframe src="https://marimo.app/l/z0aerp?embed=true" class="demo xxlarge" frameBorder="0">
</iframe>
