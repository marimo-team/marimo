<p align="center">
  <img src="https://github.com/marimo-team/marimo/raw/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>A reactive Python notebook that's reproducible, git-friendly, and deployable as scripts or apps.</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/JE7nhX6mD8" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>Examples</strong></a>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

marimo is a reactive notebook for Python. It allows you to rapidly experiment
with data and models, code with confidence in your notebook's correctness, and
productionize notebooks as pipelines or interactive web apps.


**Highlights**.

- **reactive**: run a cell, and marimo automatically updates all affected cells and outputs
- **interactive**: bind sliders, tables, plots, and more to Python — no callbacks required
- **reproducible**: no hidden state, deterministic execution order
- **executable**: execute as a Python script
- **shareable**: deploy as an app
- **git-friendly**: stored as `.py` files


```python
pip install marimo && marimo tutorial intro
```

_Jump to the [quickstart](#quickstart) for a primer on our CLI._

## A reactive programming environment


**A reactive programming environment.** Run a cell and marimo _reacts_ by
automatically running the cells that reference its variables, giving you instant feedback as
you experiment with models. Delete a cell and marimo scrubs its variables from
program memory, eliminating hidden state. 

<img src="docs/_static/reactive.gif" width="700px" />



Notebooks are executed in a deterministic order, based on variable references
instead of cells' positions on the page. Organize your notebook
to best fit the story you're telling.


**Synchronized UI elements.** Import `marimo` to use
interactive elements like sliders, dropdowns, dataframe transformers, selectable plots, and more. Interact with
an element and all cells that use it are automatically re-run with its
latest value.

<img src="docs/_static/readme-ui.gif" width="700px" />

**Performant runtime.** marimo's runtime uses static analysis to run
only those cells that need to be run. You can optionally disable expensive cells to prevent them from automatically running.

**Batteries-included.** marimo comes with GitHub Copilot, Black code
formatting, HTML export, fast code completion, a [VS Code
extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo),
and many more quality-of-life features.

## Quickstart

**Installation.** In a terminal, run

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

**Create notebooks.**
Create an empty notebook with

```bash
marimo edit
```

or create/edit a notebook with a given name with

```bash
marimo edit your_notebook.py
```


**Run apps.** Run your notebook as a web app, with Python
code hidden and
uneditable:

```bash
marimo run your_notebook.py
```

<img src="docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

_This app is deployed on [marimo cloud](https://marimo.io/cloud)._

**Execute as scripts.** marimo notebooks can be executed as scripts at the
command line:

```bash
python your_notebook.py
```

**Automatically convert Jupyter notebooks.** Automatically convert Jupyter notebooks to marimo notebooks with the CLI

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

or use our [web interface](https://marimo.io/convert).

**Tutorials.**
List all tutorials:

```bash
marimo tutorial --help
```

## Learn more

Ready to learn more? Check out our [docs](https://docs.marimo.io),
the `examples/` folder, and our [gallery](https://marimo.io/@public).

<table border="0">
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
        <img src="https://docs.marimo.io/_static/reactive.gif" style="max-height:150px; width:auto; display:block;">
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html">
        <img src="docs/_static/readme-ui.gif" style="max-height:150px; width:auto; display:block;">
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/plotting.html">
        <img src="docs/_static/docs-intro.gif" style="max-height:150px; width:auto; display:block;">
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/layouts/index.html">
        <img src="docs/_static/outputs.gif" style="max-height:150px; width:auto; display:block;">
      </a>
    </td>
    </tr>
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
	  Tutorial
	  </a>
	</td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
	  Inputs
	  </a>
	</td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
	  Plots
	  </a>
	</td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/overview.html">
	  Layout
	  </a>
	</td>
  </tr>
</table>

## FAQ

See the [FAQ](https://docs.marimo.io/faq.html) at our docs.

## Contributing

We appreciate all contributions! You don't need to be an expert to help out.
Please see [CONTRIBUTING.md](CONTRIBUTING.md) for more details on how to get
started.

> Questions? Reach out to us [on Discord](https://discord.gg/JE7nhX6mD8).

## Community

We're building a community. Come hang out with us!

- 🌟 [Star us on GitHub](https://github.com/marimo-team/marimo)
- 💬 [Chat with us on Discord](https://discord.gg/JE7nhX6mD8)
- 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
- ☁️  [Join our Cloud Waitlist](https://marimo.io/cloud)
- ✏️  [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
- 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
- 🕴️ [Follow us on LinkedIn](https://www.linkedin.com/company/marimo-io)
