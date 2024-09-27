<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>A reactive Python notebook that's reproducible, git-friendly, and deployable as scripts or apps.</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/JE7nhX6mD8" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>Examples</strong></a>
</p>

<p align="center">
  <b>English | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Chinese.md" target="_blank"><b>简体中文</b></a>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://discord.gg/JE7nhX6mD8"><img src="https://shields.io/discord/1059888774789730424" alt="discord" /></a>
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**marimo** is a reactive Python notebook: run a cell or interact with a UI
element, and marimo automatically runs dependent cells (or <a href="#expensive-notebooks">marks them as stale</a>), keeping code and outputs
consistent. marimo notebooks are stored as pure Python, executable as scripts,
and deployable as apps.

**Highlights**.

- 🚀 **batteries-included:** replaces `jupyter`, `streamlit`, `jupytext`, `ipywidgets`, `papermill`, and more
- ⚡️ **reactive**: run a cell, and marimo reactively [runs all dependent cells](https://docs.marimo.io/guides/reactivity.html) or <a href="#expensive-notebooks">marks them as stale</a>
- 🖐️ **interactive:** [bind sliders, tables, plots, and more](https://docs.marimo.io/guides/interactivity.html) to Python — no callbacks required
- 🔬 **reproducible:** [no hidden state](https://docs.marimo.io/guides/reactivity.html#no-hidden-state), deterministic execution, [built-in package management](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **executable:** [execute as a Python script](https://docs.marimo.io/guides/scripts.html), parametrized by CLI args
- 🛜 **shareable**: [deploy as an interactive web app](https://docs.marimo.io/guides/apps.html) or [slides](https://docs.marimo.io/guides/apps.html#slides-layout), [run in the browser via WASM](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **designed for data**: query dataframes and databases [with SQL](https://docs.marimo.io/guides/sql.html), filter and search [dataframes](https://docs.marimo.io/guides/dataframes.html#displaying-dataframes)
- 🐍 **git-friendly:** notebooks are stored as `.py` files
- ⌨️ **a modern editor**: [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot), [AI assistants](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama), vim keybindings, variable explorer, and [more](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_Try marimo at [our online playground](https://marimo.app/l/c7h6pz), which runs entirely in the browser!_

_Jump to the [quickstart](#quickstart) for a primer on our CLI._

## A reactive programming environment

marimo guarantees your notebook code, outputs, and program state are consistent. This [solves many problems](https://docs.marimo.io/faq.html#faq-problems) associated with traditional notebooks like Jupyter.

**A reactive programming environment.**
Run a cell and marimo _reacts_ by automatically running the cells that
reference its variables, eliminating the error-prone task of manually
re-running cells. Delete a cell and marimo scrubs its variables from program
memory, eliminating hidden state.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**Compatible with expensive notebooks.** marimo lets you configure the runtime
to be lazy, marking affected cells as stale instead of automatically running
them. This gives you guarantees on program state while preventing accidental
execution of expensive cells.

**Synchronized UI elements.** Interact with UI elements like sliders,
dropdowns, and dataframe transformers, and the cells that use them are
automatically re-run with their latest values.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**Performant runtime.** marimo runs only those cells that need to be run by
statically analyzing your code.

**Dynamic markdown and SQL.** Use markdown to tell dynamic stories that depend on
Python data. Or build [SQL](https://docs.marimo.io/guides/sql.html) queries
that depend on Python values and execute them against dataframes, databases,
CSVs, Google Sheets, or anything else using our built-in SQL engine, which
returns the result as a Python dataframe.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

Your notebooks are still pure Python, even if they use markdown or SQL.

**Deterministic execution order.** Notebooks are executed in a deterministic
order, based on variable references instead of cells' positions on the page.
Organize your notebooks to best fit the stories you'd like to tell.

**Built-in package management.** marimo has built-in support for all major
package managers, letting you install packages on import. marimo can even
[serialize package
requirements](https://docs.marimo.io/guides/editor_features/package_management.html#auto-add-inline-script-metadata-uv-only)
in notebook files, and auto install them in
[isolated venv sandboxes](https://docs.marimo.io/guides/editor_features/package_management.html#running-marimo-in-a-sandbox-environment-uv-only).

**Batteries-included.** marimo comes with GitHub Copilot, AI assistants, Ruff
code formatting, HTML export, fast code completion, a [VS Code
extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo),
an interactive dataframe viewer, and [many more](https://docs.marimo.io/guides/editor_features/index.html)
quality-of-life features.

## Quickstart

**Installation.** In a terminal, run

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
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

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

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

See the [FAQ](https://docs.marimo.io/faq.html) at our docs.

## Learn more

marimo is easy to get started with, with lots of room for power users.
For example, here's an embedding visualizer made in marimo
([video](https://marimo.io/videos/landing/full.mp4)):

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

Check out our [docs](https://docs.marimo.io),
the `examples/` folder, and our [gallery](https://marimo.io/@public) to learn more.

<table border="0">
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
        <img src="https://docs.marimo.io/_static/reactive.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/plotting.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-intro.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/outputs.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
  </tr>
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html"> Tutorial </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> Inputs </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/plotting.html"> Plots </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html"> Layout </a>
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

> Questions? Reach out to us [on Discord](https://discord.gg/JE7nhX6mD8).

## Community

We're building a community. Come hang out with us!

- 🌟 [Star us on GitHub](https://github.com/marimo-team/marimo)
- 💬 [Chat with us on Discord](https://discord.gg/JE7nhX6mD8)
- 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
- ☁️ [Join our Cloud Waitlist](https://marimo.io/cloud)
- ✏️ [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
- 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
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
