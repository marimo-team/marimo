# FAQ

- [Choosing marimo](#choosing-marimo)
  - [How is marimo different from Jupyter?](#faq-jupyter)
  - [How is marimo.ui different from Jupyter widgets?](#faq-widgets)
- [Using marimo](#using-marimo)
  - [Is marimo a notebook or a library?](#faq-notebook-or-library)
  - [How does marimo know what cells to run?](#faq-reactivity)
  - [How do I use sliders and other interactive elements?](#faq-interactivity)
  - [How do I add a submit button to UI elements?](#faq-form)
  - [How do I write markdown?](#faq-markdown)
  - [How do I display plots?](#faq-plots)
  - [How do I display objects in rows and columns?](#faq-rows-columns)
  - [What packages can I use?](#faq-packages)
  - [What's the difference between a marimo notebook and a marimo app?](#faq-notebook-app)
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

<a name="faq-interactivity" ></a>
**How do I use sliders and other interactive elements?**

Interactive UI elements like sliders are available in `marimo.ui`.

- Assign the UI element to a global variable (`slider = mo.ui.slider(0,
  100)`)
- Include it in the last expression of a cell to display
it (`slider` or `mo.md(f"Choose a value: {slider}")`)
- Read its current value in another cell via its `value` attribute (`slider.value`)

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

<a name="faq-rows-columns" ></a>
**How do I display objects in rows and columns?**

Use `marimo.hstack` and `marimo.vstack`. See the layout tutorial for details:

```bash
marimo tutorial layout
```
<a name="faq-packages" ></a>
**What packages can I use?**

You can use any Python package. marimo cells run arbitrary Python code.

<a name="faq-notebook-app" ></a>
**What's the difference between a marimo notebook and a marimo app?**

You can think of marimo programs as notebooks, apps, or both. Edit a marimo
program as notebook with `marimo edit`, or run it as an app, rendering cell
outputs without their code, with `marimo run`.

<a name="faq-app-deploy" ></a>
**How do I deploy apps?**

Use the marimo CLI's `run` command to serve a notebook as an app:

```
marimo run notebook.py
```

<a name="faq-marimo-free" ></a>
**Is marimo free?**

Yes!


