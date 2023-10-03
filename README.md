<p align="center">
  <img src="https://github.com/marimo-team/marimo/raw/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  A next-generation Python notebook: <em>explore data, build tools, deploy apps!</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/JE7nhX6mD8" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>Examples</strong></a>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**marimo** is a next-generation Python notebook where every notebook is
also shareable as an interactive web app: _explore data, run
experiments, build tools, and deploy apps, all from one seamless
environment_.


**Highlights.** marimo is purpose-built for working with data in Python. Some key features:

- **reactive**: run a cell, and marimo automatically runs cells that depend on it
- **interactive**: connect inputs like sliders, dropdowns, tables, and
  more to Python
- **expressive**: create dynamic makdown parametrized by interactive elements, plots, or anything else
- **simple**: no callbacks, no magical syntax — just Python
- **Pythonic**: cells only run Python; notebooks stored as `.py` files (clean git diffs!)
- **performant**: powered by static analysis, zero runtime overhead

marimo was built from the ground up to solve many [well-known problems
with traditional notebooks](https://docs.marimo.io/faq.html#faq-jupyter).
marimo is _not_ built on top of Jupyter or any other notebook or app library.

![marimo](https://github.com/marimo-team/marimo/blob/main/docs/_static/intro_condensed.gif)

**Contents.**

<!-- toc -->

- [Getting Started](#getting-started)
  - [Installation](#installation)
  - [Tutorials](#tutorials)
  - [Notebooks](#notebooks)
  - [Apps](#apps)
  - [Convert Jupyter notebooks](#convert-jupyter-notebooks)
  - [Github Copilot](#github-copilot)
  - [VS Code extension](#vs-code-extension)
- [Concepts](#concepts)
- [Examples](#examples)
- [FAQ](#faq)
- [Contributing](#contributing)
- [Community](#community)

<!-- tocstop -->

## Getting Started

Installing marimo gets you the `marimo` command-line interface (CLI), the entry point to all things marimo.

### Installation

In a terminal, run

```bash
pip install marimo
marimo tutorial intro
```

You should see a tutorial notebook in your browser:

<div align="center">
<img src="https://github.com/marimo-team/marimo/blob/main/docs/_static/intro_tutorial.gif" width="400px" />
</div>

If that doesn't work, please [open a Github issue](https://github.com/marimo-team/marimo/issues).

### Tutorials

`marimo tutorial intro` opens the intro tutorial. List all tutorials with

```bash
marimo tutorial --help
```

### Notebooks

Create and edit notebooks with `marimo edit`.

- create a new notebook:

```bash
marimo edit
```

- create or edit a notebook with a given name:

```bash
marimo edit your_notebook.py
```

### Apps

Use `marimo run` to serve your notebook as an app, with Python code hidden and
uneditable.

```bash
marimo run your_notebook.py
```

### Convert Jupyter notebooks

Automatically translate Jupyter notebooks to marimo notebooks with `marimo convert`:

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

Because marimo is different from traditional notebooks, your converted
notebook will likely have errors that you'll need to fix. marimo
will guide you through fixing them when you open it with `marimo edit`.

### Github Copilot

The marimo editor natively supports [Github Copilot](https://copilot.github.com/),
an AI pair programmer, similar to VS Code.

_Get started with Copilot_:

1. Install [Node.js](https://nodejs.org/en/download).
2. Enable Copilot via the settings menu in the marimo editor.

### VS Code extension

If you prefer VS Code over terminal, try our
[VS Code extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo).
Use the extension to edit and run notebooks directly from VS Code, and to list
all marimo notebooks in your current directory.

## Concepts

marimo notebooks are **reactive**: they automatically react to your code
changes and UI interactions and keep your notebook up-to-date (like a
spreadsheet).

### Cells

A marimo notebook is made of small blocks of Python code called **cells**.
_When you run a cell, marimo automatically runs all cells that read any global
variables defined by that cell._ This is reactive execution.

> **Reactive execution lets your notebooks double as interactive
apps**. It also guarantees that your code and program state are
consistent.

<div align="center">
<figure>
<img src="https://github.com/marimo-team/marimo/blob/main/docs/_static/reactive.gif" width="600px"/>
</figure>
</div>

**Execution order.**
The order of cells on the page has no bearing on the order cells are
executed in: execution order is completely determined by the variables
cells define and the cells they read. You have full freedom over
how to organize your code and tell your stories: move helper functions and
other "appendices" to the bottom of your notebook, or put cells with important
outputs at the top.

**No hidden state.**
marimo notebooks have no hidden state because the program state is
automatically synchronized with your code changes and UI interactions. And if
you delete a cell, marimo automatically deletes that cell's variables,
preventing painful bugs that arise in traditional notebooks.

**No magical syntax.**
There's no magical syntax or API required to opt-in to reactivity: cells are
Python and _only Python_. Behind-the-scenes, marimo statically analyzes each
cell's code just once, creating a directed acyclic graph based on the
global names each cell defines and reads. This is how data flows
in a marimo notebook.

For more on reactive execution, open the dataflow tutorial:

```bash
marimo tutorial dataflow
```

### The marimo library

marimo is both a notebook and a library. The marimo library lets you use
markdown, interactive UI elements, layout elements, and more in your marimo
notebooks.

We recommend starting each marimo notebook with a cell containing a single
line of code,

```python3
import marimo as mo
```

### Outputs

marimo visualizes the last expression of each cell as its **output**. Outputs
can be any Python value, including markdown and interactive elements created
with the marimo library, _e.g._, `mo.md(...)`, `mo.ui.slider(...)`.
You can even interpolate Python values into markdown and other marimo elements
to build rich composite outputs.

<div align="center">
<figure>
<img src="https://github.com/marimo-team/marimo/blob/main/docs/_static/outputs.gif" width="600px"/>
</figure>
</div>

> Thanks to reactive execution, running a cell refreshes all the relevant outputs in your notebook.

For more on outputs, try these tutorials:

```bash
marimo tutorial markdown
marimo tutorial plots
marimo tutorial layout
```

### Interactive elements

The marimo library comes with many interactive stateful elements in
`marimo.ui`, including simple ones like sliders, dropdowns, text fields, and file
upload areas, as well as composite ones like forms, arrays, and dictionaries
that can wrap other UI elements.

<div align="center">
<figure>
<img src="https://github.com/marimo-team/marimo/blob/main/docs/_static/readme-ui.gif" width="600px"/>
</figure>
</div>

**Using UI elements.**
To use a UI element, create it with `marimo.ui` and **assign it to a global
variable.** When you interact with a UI element in your browser (_e.g._,
sliding a slider), _marimo sends the new value back to Python and reactively
runs all cells that use the element_, which you can access via its `value`
attribute.

> **This combination of interactivity and reactivity is very powerful**: use it
to make your data tangible during exploration and to build all kinds of tools
and apps.

_marimo can only synchronize UI elements that are assigned to
global variables._ You can use composite elements like `mo.ui.array` and
`mo.ui.dictionary` if the set of UI elements is not known until runtime.

For more on interactive elements, run the UI tutorial:

```bash
marimo tutorial ui
```

#### Composite elements

marimo's composite UI elements let you wrap other UI
elements to create powerful UIs. For example,
`marimo.ui.form` lets you gate elements on submission, while
`marimo.ui.dictionary` and `marimo.ui.array` let you batch arbitrary
collections of elements.

<div align="center">
<figure>
<img src="https://github.com/marimo-team/marimo/blob/main/docs/_static/readme-ui-form.gif" width="600px"/>
</figure>
</div>

### Layout

The marimo library also comes with layout elements, including `mo.hstack`,
`mo.vstack`, and `mo.tabs`. See the [API reference](https://docs.marimo.io/api/layouts/index.html) for more info.

## Examples

Examples are available in the `examples/` directory. Community examples can be
found and shared in the [marimo cookbook](https://github.com/marimo-team/cookbook).

We've deployed many of these examples at our [public
gallery](https://marimo.io/@public); try them out!

## FAQ

See the [FAQ](https://docs.marimo.io/faq.html) at our docs.

## Contributing

We appreciate all contributions. You don't need to be an expert to help out.
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for more details on how to get
started.

> Questions? Reach out to us [on Discord](https://discord.gg/JE7nhX6mD8).

## Community

We're building a community. Come hang out with us!

- 🌟 [Star us on GitHub](https://github.com/marimo-team/marimo)
- 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
- 💬 [Join us on Discord](https://discord.gg/JE7nhX6mD8)
- 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
- 🕴️ [Follow us on LinkedIn](https://www.linkedin.com/company/marimo-io)
- ✏️ [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
