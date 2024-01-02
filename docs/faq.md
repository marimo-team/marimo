# FAQ

- [Choosing marimo](#choosing-marimo)
  - [How is marimo different from Jupyter?](#faq-jupyter)
  - [How is marimo.ui different from Jupyter widgets?](#faq-widgets)
- [Using marimo](#using-marimo)
  - [Is marimo a notebook or a library?](#faq-notebook-or-library)
  - [What's the difference between a marimo notebook and a marimo app?](#faq-notebook-app)
  - [How does marimo know what cells to run?](#faq-reactivity)
  - [How do I prevent automatic execution from running expensive cells?](#faq-expensive)
  - [How do I use sliders and other interactive elements?](#faq-interactivity)
  - [How do I add a submit button to UI elements?](#faq-form)
  - [How do I write markdown?](#faq-markdown)
  - [How do I display plots?](#faq-plots)
  - [How do I prevent matplotlib plots from being cut off?](#faq-mpl-cutoff)
  - [How do I display interactive matplotlib plots?](#faq-interactive-plots)
  - [How do I display objects in rows and columns?](#faq-rows-columns)
  - [How do I create an output with a dynamic number of UI elements?](#faq-dynamic-ui-elements)
  - [Why aren't my `on_change` handlers being called?](#faq-on-change-called)
  - [How do I restart a notebook?](#faq-restart)
  - [How do I reload modules?](#faq-reload)
  - [How does marimo treat type annotations?](#faq-annotations)
  - [What packages can I use?](#faq-packages)
  - [How do I use marimo on a remote server?](#faq-remote)
  - [How do I deploy apps?](#faq-app-deploy)
  - [Is marimo free?](#faq-marimo-free)

## Choosing marimo

<a name="faq-jupyter" ></a>
**How is marimo different from Jupyter?**

marimo is a brand new Python notebook that is both _interactive_, with 
UI elements like sliders, dropdowns, etc., and _reactive_, like a
spreadsheet. marimo solves many well-documented problems associated with
traditional notebooks like Jupyter
[[1]](https://austinhenley.com/pubs/Chattopadhyay2020CHI_NotebookPainpoints.pdf)
[[2]](https://docs.google.com/presentation/d/1n2RlMdmv1p25Xy5thJUhkKGvjtV-dkAIsUXP-AL4ffI/edit#slide=id.g362da58057_0_1):

- **no hidden state**: running a cell automatically runs all
  cells that depend on it, and deleting a cell automatically deletes its
variables, eliminating hidden state and hidden bugs
- **interactive data exploration**: UI elements and reactivity make your data
  tangible
- **sharing**: use the marimo CLI to run notebooks as apps
- **Python, not JSON**: stored as executable Python, with clean git diffs
  and potential for code reuse
- **fast, reliable autocomplete**: code completion is fast and works out of the
  box


<a name="faq-widgets" ></a>
**How is `marimo.ui` different from Jupyter widgets?**


Unlike Jupyter widgets, marimo's interactive elements are automatically
synchronized with the Python kernel: no callbacks, no observers, no manually
re-running cells.


<p align="center">
<img src="/_static/faq-marimo-ui.gif" width="600px" />
</p>

## Using marimo

**Is marimo a notebook or a library?**

marimo is both a notebook and a library.

- Create _marimo notebooks_ with the editor that opens in your
  browser when you run `marimo edit`.
- Use the _marimo library_ (`import marimo as mo`) in
  marimo notebooks. Write markdown with `mo.md(...)`,
  create stateful interactive elements with `mo.ui` (`mo.ui.slider(...)`), and
  more. See the docs for an [API reference](https://docs.marimo.io/api/).

<a name="faq-notebook-app" ></a>
**What's the difference between a marimo notebook and a marimo app?**

marimo programs are notebooks, apps, or both, depending on how you use them.

There are two ways to interact with a marimo program:

1. open it as a computational _notebook_ with `marimo edit`
2. run it as an interactive _app_ with `marimo run`

All marimo programs start as notebooks, since they are created with `marimo
edit`. Because marimo notebooks are reactive and have built-in interactive
elements, many can easily be made into useful and beautiful apps by simply
hiding the notebook code: this is what `marimo run` does.

Not every notebook needs to be run as an app — marimo notebooks are useful in
and of themselves for rapidly exploring data and doing reproducible science.
And not every app is improved by interacting with the notebook. In some
settings, such as collaborative research, education, and technical
presentations, going back and forth between the notebook view and app view
(which you can do from `marimo edit`) can be useful!

<a name="faq-reactivity" ></a>
**How does marimo know what cells to run?**

marimo reads each cell once to determine what global names it defines and what
global names it reads. When a cell is run, marimo runs all other cells that
read any of the global names it defines. A global name can refer to a variable,
class, function, or import. 

In other words, marimo uses _static analysis_ to make a dataflow graph out of
your cells. Each cell is a node in the graph across which global
variables "flow". Whenever a cell is run, either because you changed its
code or interacted with a UI element it reads, all its descendants run in turn.

<a name="faq-expensive"></a>

**How do I prevent automatic execution from running expensive cells?**

Reactive (automatic) execution ensures your code and outputs are always
in sync, improving reproducibility by eliminating hidden state and
out-of-order execution; marimo also takes care to run only the minimal set of
cells needed to keep your notebook up to date. But when some cells take a long
time to run, it's understandable to be concerned that automatic execution will
kick off expensive cells before you're ready to run them.

_Here are some tips to avoid accidental execution of expensive cells:_

- [Disable expensive cells](guides/reactivity.md#disabling-cells).
When a cell is disabled, it and its descendants are blocked from running.
- Use Python's `functools.cache` to cache expensive
intermediate computations (see our [best practices guide](guides/best_practices.md)).
- Wrap UI elements in a [form](api/inputs/form.md#marimo.ui.form).
- Use [`mo.stop`](api/control_flow.md#marimo.stop) to conditionally stop
  execution of a cell and its descendants.

<a name="faq-interactivity" ></a>
**How do I use sliders and other interactive elements?**

Interactive UI elements like sliders are available in `marimo.ui`.

- Assign the UI element to a global variable (`slider = mo.ui.slider(0,
  100)`)
- Include it in the last expression of a cell to display
it (`slider` or `mo.md(f"Choose a value: {slider}")`)
- Read its current value in another cell via its `value` attribute (`slider.value`)

_When a UI element bound to a global variable is interacted with, all cells
referencing the global variable are run automatically_.

If you have many UI elements or don't know the elements
you'll create until runtime, use `marimo.ui.array` and `marimo.ui.dictionary`
to create UI elements that wrap other UI elements (`sliders =
mo.ui.array([slider(1, 100) for _ in range(n_sliders)])`).

All this and more is explained in the UI tutorial. Run it with

```bash
marimo tutorial ui
```

at the command line.

<a name="faq-form" ></a>
**How do I add a submit button to UI elements?**

Use the `form` method to add a submit button to a UI element. For
example,

```python
form = marimo.ui.text_area().form()
```
 When wrapped in a form, the
text area's value will only be sent to Python when you click the submit button.
Access the last submitted value of the text area with `form.value`.

<a name="faq-markdown" ></a>
**How do I write markdown?**

Import `marimo` (as `mo`) in a notebook, and use the `mo.md` function.


<a name="faq-plots" ></a>
**How do I display plots?**

Include plots in the last expression of a cell to display them, just like all
other outputs. If you're using matplotlib, you can display the `Figure` object
(get the current figure with `plt.gcf()`). For examples, run the plots tutorial:

```bash
marimo tutorial plots
```

Also see the <a href="/api/plotting.html">plotting API reference</a>.

<a name="faq-mpl-cutoff" ></a>
**How do I prevent matplotlib plots from being cut off?**

If your legend or axes labels are cut off, try calling `plt.tight_layout()`
before outputting your plot:

```python
import matplotlib.pyplot as plt

plt.plot([-8, 8])
plt.ylabel("my variable")
plt.tight_layout()
plt.gca()
```

<a name="faq-interactive-plots" ></a>
**How do I display interactive matplotlib plots?**

Use <a href="/api/plotting.html#marimo.mpl.interactive">`marimo.mpl.interactive`</a>.

```bash
fig, ax = plt.subplots()
ax.plot([1, 2])
mo.mpl.interactive(ax)
```

<a name="faq-rows-columns" ></a>
**How do I display objects in rows and columns?**

Use `marimo.hstack` and `marimo.vstack`. See the layout tutorial for details:

```bash
marimo tutorial layout
```

<a name="faq-dynamic-ui-elements"></a>
**How do I create an output with a dynamic number of UI elements?**

Use [`mo.ui.array`](/api/inputs/array.md#marimo.ui.array),
[`mo.ui.dictionary`](/api/inputs/dictionary.md#marimo.ui.dictionary), or
[`mo.ui.batch`](/api/inputs/batch.md#marimo.ui.batch) to create a UI element
that wraps a dynamic number of other UI elements.

If you need custom
formatting, use [`mo.ui.batch`](/api/inputs/batch.md#marimo.ui.batch), otherwise
use [`mo.ui.array`](/api/inputs/array.md#marimo.ui.array) or
[`mo.ui.dictionary`](/api/inputs/dictionary.md#marimo.ui.dictionary).

For usage examples, see the
[recipes for grouping UI elements together](/recipes.md#grouping-ui-elements-together).

<a name="faq-restart" ></a>
**How do I restart a notebook?**

To clear all program memory and restart the notebook from scratch, refresh
the browser page.

<a name="faq-reload" ></a>
**How do I reload modules?**

To reload modules, use
[`importlib.reload()`](https://docs.python.org/3/library/importlib.html#importlib.reload):

```
import mymodule
import importlib
importlib.reload(mymodule)
```

Running this cell will reload `mymodule` with your new edits and automatically
re-run any cells using `mymodule`.

<a name="faq-on-change-called"></a>
**Why aren't my `on_change`/`on_click` handlers being called?**

A UI Element's `on_change` (or for buttons, `on_click`) handlers are only
called if the element is bound to a global variable. For example, this won't work

```python
mo.vstack([mo.ui.button(on_change=lambda _: print('I was called")) for _ in range(10)])
```

In such cases (when you want to output a dynamic number of UI elements),
you need to use 
[`mo.ui.array`](/api/inputs/array.md#marimo.ui.array),
[`mo.ui.dictionary`](/api/inputs/dictionary.md#marimo.ui.dictionary), or
[`mo.ui.batch`](/api/inputs/batch.md#marimo.ui.batch).

See the
[recipes for grouping UI elements together](/recipes.md#grouping-ui-elements-together)
for example code.

<a name="faq-annotations"></a>
**How does marimo treat type annotations?**

Type annotations are registered as references of a cell, unless they
are explicitly written as strings. This helps ensure correctness of code that
depends on type annotations at runtime (_e.g._, Pydantic), while still
providing a way to omit annotations from affecting dataflow graph.


For example, in

```python
x: A = ...
```

`A` is treated as a reference, used in determining the dataflow graph, but
in

```python
x: "A" = ...
```

`A` isn't made a reference.

For Python 3.12+, marimo additionally implements annotation scoping.

<a name="faq-packages" ></a>
**What packages can I use?**

You can use any Python package. marimo cells run arbitrary Python code.

<a name="faq-remote" ></a>
**How do I use marimo on a remote server?**

Use SSH port-forwarding to run the marimo kernel on a remote server
and connect to it from a browser on your local machine. Make sure
to pass the `--headless` flag when starting marimo on remote:

```bash
marimo edit notebook.py --headless
```

<a name="faq-app-deploy" ></a>
**How do I deploy apps?**

Use the marimo CLI's `run` command to serve a notebook as an app:

```
marimo run notebook.py
```

<a name="faq-marimo-free" ></a>
**Is marimo free?**

Yes!


