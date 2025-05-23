---
hide:
  - navigation
---
<style>
  .md-typeset h1,
  .md-content__button {
    display: none;
  }
</style>

<p align="center" style="margin-top: 40px; margin-bottom: 40px;">
  <img src="_static/marimo-logotype-thick.svg" width="210px">
</p>

marimo is a reactive Python notebook: run a cell or interact with a UI
element, and marimo automatically runs dependent cells (or [marks them as
stale](guides/reactivity.md#configuring-how-marimo-runs-cells)), keeping code and outputs
consistent and preventing bugs before they happen. Every marimo notebook is
stored as pure Python (Git-friendly), executable as a script, and deployable as an app.

/// admonition | Built from the ground up
    type: tip

marimo was built from the ground up to solve <a href="faq.html#faq-jupyter">well-known problems associated with traditional notebooks</a>.
///

/// tab | install with pip

```bash
pip install marimo && marimo tutorial intro
```

///

/// tab | install with uv

```bash
uv add marimo && uv run marimo tutorial intro
```

///

/// tab | install with conda

```bash
conda install -c conda-forge marimo && marimo tutorial intro
```

///

Developer experience is core to marimo, with an emphasis on
reproducibility, maintainability, composability, and shareability.

## Highlights

- 🚀 **batteries-included:** replaces `jupyter`, `streamlit`, `jupytext`, `ipywidgets`, `papermill`, and more
- ⚡️ **reactive**: run a cell, and marimo reactively [runs all dependent cells](guides/reactivity.md) or <a href="#expensive-notebooks">marks them as stale</a>
- 🖐️ **interactive:** [bind sliders, tables, plots, and more](guides/interactivity.md) to Python — no callbacks required
- 🐍 **git-friendly:** stored as `.py` files
- 🛢️ **designed for data**: query dataframes, databases, warehouses, and lakehouses [with SQL](guides/working_with_data/sql.md); filter and search [dataframes](guides/working_with_data/dataframes.md)
- 🔬 **reproducible:** [no hidden state](guides/reactivity.md), deterministic execution, [built-in package management](guides/editor_features/package_management.md)
- 🏃 **executable:** [execute as a Python script](guides/scripts.md), parameterized by CLI args
- 🛜 **shareable**: [deploy as an interactive web app](guides/apps.md) or [slides](guides/apps.md#slides-layout), [run in the browser via WASM](guides/wasm.md)
- 🧩 **reusable:** [import functions and classes](guides/reusing_functions.md) from one notebook to another
- 🧪 **testable:** [run pytest](guides/testing/index.md) on notebooks
- ⌨️ **a modern editor**: [GitHub Copilot](guides/editor_features/ai_completion.md#github-copilot), [AI assistants](guides/editor_features/ai_completion.md#using-ollama), vim keybindings, variable explorer, and [more](guides/editor_features/index.md)

## A reactive programming environment

marimo guarantees your notebook code, outputs, and program state are consistent. This [solves many problems](faq.md#faq-problems) associated with traditional notebooks like Jupyter.

**A reactive programming environment.**
Run a cell and marimo _reacts_ by automatically running the cells that
reference its variables, eliminating the error-prone task of manually
re-running cells. Delete a cell and marimo scrubs its variables from program
memory, eliminating hidden state.

<video autoplay muted loop playsinline width="700px" align="center">
  <source src="/_static/reactive.mp4" type="video/mp4">
  <source src="/_static/reactive.webm" type="video/webm">
</video>

<a name="expensive-notebooks"></a>

**Compatible with expensive notebooks.** marimo lets you [configure the runtime
to be
lazy](guides/configuration/runtime_configuration.md),
marking affected cells as stale instead of automatically running them. This
gives you guarantees on program state while preventing accidental execution of
expensive cells.

**Synchronized UI elements.** Interact with [UI
elements](guides/interactivity.md) like [sliders](api/inputs/slider.md#slider),
[dropdowns](api/inputs/dropdown.md), [dataframe
transformers](api/inputs/dataframe.md), and [chat
interfaces](api/inputs/chat.md), and the cells that
use them are automatically re-run with their latest values.

<video autoplay muted loop playsinline width="700px" align="center">
  <source src="/_static/readme-ui.mp4" type="video/mp4">
  <source src="/_static/readme-ui.webm" type="video/webm">
</video>

**Interactive dataframes.** [Page through, search, filter, and
sort](./guides/working_with_data/dataframes.md)
millions of rows blazingly fast, no code required.

<video autoplay muted loop playsinline width="100%" height="100%" align="center">
  <source src="/_static/docs-df.mp4" type="video/mp4">
  <source src="/_static/docs-df.webm" type="video/webm">
</video>

**Performant runtime.** marimo runs only those cells that need to be run by
statically analyzing your code.

**Dynamic markdown and SQL.** Use markdown to tell dynamic stories that depend on
Python data. Or build [SQL](guides/working_with_data/sql.md) queries
that depend on Python values and execute them against dataframes, databases,
CSVs, Google Sheets, or anything else using our built-in SQL engine, which
returns the result as a Python dataframe.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

Your notebooks are still pure Python, even if they use markdown or SQL.

**Deterministic execution order.** Notebooks are executed in a deterministic
order, based on variable references instead of cells' positions on the page.
Organize your notebooks to best fit the stories you'd like to tell.

**Built-in package management.** marimo has built-in support for all major
package managers, letting you [install packages on import](guides/editor_features/package_management.md). marimo can even
[serialize package
requirements](guides/package_reproducibility.md)
in notebook files, and auto install them in
isolated venv sandboxes.

**Batteries-included.** marimo comes with GitHub Copilot, AI assistants, Ruff
code formatting, HTML export, fast code completion, a [VS Code
extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo),
an interactive dataframe viewer, and [many more](guides/editor_features/index.md)
quality-of-life features.

## Quickstart

**Installation.** In a terminal, run

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

To install with additional dependencies that unlock SQL cells, AI completion, and more,
run

```bash
pip install marimo[recommended]
```

**Create notebooks.**

Create or edit notebooks with

```bash
marimo edit
```

**Run apps.** Run your notebook as a web app, with Python
code hidden and uneditable:

```bash
marimo run your_notebook.py
```

<video autoplay muted loop playsinline width="450px" align="center" style="border-radius: 8px">
  <source src="/_static/docs-model-comparison.mp4" type="video/mp4">
  <source src="/_static/docs-model-comparison.webm" type="video/webm">
</video>

**Execute as scripts.** Execute a notebook as a script at the
command line:

```bash
python your_notebook.py
```

**Automatically convert Jupyter notebooks.** Automatically convert Jupyter
notebooks to marimo notebooks with the CLI

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

or use our [web interface](https://marimo.io/convert).

**Tutorials.**
List all tutorials:

```bash
marimo tutorial --help
```

## Questions?

See our [FAQ](faq.md).

## Learn more

marimo is easy to get started with, with lots of room for power users.
For example, here's an embedding visualizer made in marimo
([video](https://marimo.io/videos/landing/full.mp4)):

<video autoplay muted loop playsinline width="700px" align="center">
  <source src="/_static/embedding.mp4" type="video/mp4">
  <source src="/_static/embedding.webm" type="video/webm">
</video>

Check out our [guides](guides/index.md), [usage examples](examples/index.md),
and our [gallery](https://marimo.io/gallery) to learn more.

<table border="0">
  <tr>
    <td>
      <a target="_blank" href="getting_started/key_concepts">
        <video autoplay muted loop playsinline style="max-height: 150px; width: auto; display: block">
          <source src="/_static/reactive.mp4" type="video/mp4">
          <source src="/_static/reactive.webm" type="video/webm">
        </video>
      </a>
    </td>
    <td>
      <a target="_blank" href="api/inputs/">
        <video autoplay muted loop playsinline style="max-height: 150px; width: auto; display: block">
          <source src="/_static/readme-ui.mp4" type="video/mp4">
          <source src="/_static/readme-ui.webm" type="video/webm">
        </video>
      </a>
    </td>
    <td>
      <a target="_blank" href="guides/working_with_data/plotting">
        <video autoplay muted loop playsinline style="max-height: 150px; width: auto; display: block">
          <source src="/_static/docs-intro.mp4" type="video/mp4">
          <source src="/_static/docs-intro.webm" type="video/webm">
        </video>
      </a>
    </td>
    <td>
      <a target="_blank" href="api/layouts/">
        <video autoplay muted loop playsinline style="max-height: 150px; width: auto; display: block">
          <source src="/_static/outputs.mp4" type="video/mp4">
          <source src="/_static/outputs.webm" type="video/webm">
        </video>
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a target="_blank" href="getting_started/key_concepts"> Tutorial </a>
    </td>
    <td>
      <a target="_blank" href="api/inputs/"> Inputs </a>
    </td>
    <td>
      <a target="_blank" href="guides/working_with_data/plotting"> Plots </a>
    </td>
    <td>
      <a target="_blank" href="api/layouts/"> Layout </a>
    </td>
  </tr>
  <tr>
    <td>
      <a target="_blank" href="https://marimo.app/l/c7h6pz">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://marimo.app/l/0ue871">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://marimo.app/l/lxp1jk">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
    <td>
      <a target="_blank" href="https://marimo.app/l/14ovyr">
        <img src="https://marimo.io/shield.svg"/>
      </a>
    </td>
  </tr>
</table>

## Contributing

We appreciate all contributions! You don't need to be an expert to help out.
Please see [CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) for more details on how to get
started.

> Questions? Reach out to us [on Discord](https://marimo.io/discord?ref=docs).

## Community

We're building a community. Come hang out with us!

- 🌟 [Star us on GitHub](https://github.com/marimo-team/marimo)
- 💬 [Chat with us on Discord](https://marimo.io/discord?ref=docs)
- 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
- ☁️ [Join our Cloud Waitlist](https://marimo.io/cloud)
- ✏️ [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
- 💬 [Follow us on Bluesky](https://bsky.app/profile/marimo.io)
- 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
- 🎥 [Subscribe on YouTube](https://www.youtube.com/@marimo-team)
- 💬 [Follow us on Mastodon](https://mastodon.social/@marimo_io)
- 🕴️ [Follow us on LinkedIn](https://www.linkedin.com/company/marimo-io)

## Inspiration ✨

marimo is a **reinvention** of the Python notebook as a reproducible, interactive,
and shareable Python program, instead of an error-prone JSON scratchpad.

We believe that the tools we use shape the way we think — better tools, for
better minds. With marimo, we hope to provide the Python community with a
better programming environment to do research and communicate it; to experiment
with code and share it; to learn computational science and teach it.

Our inspiration comes from many places and projects, especially
[Pluto.jl](https://github.com/fonsp/Pluto.jl),
[ObservableHQ](https://observablehq.com/tutorials), and
[Bret Victor's essays](http://worrydream.com/). marimo is part of
a greater movement toward reactive dataflow programming. From
[IPyflow](https://github.com/ipyflow/ipyflow), [streamlit](https://github.com/streamlit/streamlit),
[TensorFlow](https://github.com/tensorflow/tensorflow),
[PyTorch](https://github.com/pytorch/pytorch/tree/main),
[JAX](https://github.com/google/jax), and
[React](https://github.com/facebook/react), the ideas of functional,
declarative, and reactive programming are transforming a broad range of tools
for the better.

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
