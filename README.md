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
- **git-friendly**: stored as `.py` files
- **deployable**: executable as a script, deployable as an app


```python
pip install marimo && marimo tutorial intro
```

![marimo](https://github.com/marimo-team/marimo/assets/1994308/59cecbb4-7c4c-4b9b-baae-e98ed209c3bb)

_Watch the animated GIF as a video at [this link](https://marimo.io/videos/landing/full.mp4)._


## Quickstart

**Installation.** In a terminal, run

```bash
pip install marimo
marimo tutorial intro
```

You should see a tutorial notebook in your browser.

marimo is also available through Conda: `conda install -c conda-forge marimo`.

**Create notebooks.**
Create an empty notebook with

```bash
marimo edit
```

or create/edit a notebook with a given name with

```bash
marimo edit your_notebook.py
```

- marimo **reacts** to your code changes, like a spreadsheet! This rapid feedback
ensures your code and outputs are always in sync.

<img src="docs/_static/reactive.gif" width="700px" />

- Import `marimo` in your notebooks to use
**interactive** elements, like sliders, dropdowns, tables, and more.

<img src="docs/_static/readme-ui.gif" width="700px" />

_See our [docs](https://docs.marimo.io/api/index.html) to learn more, including
how to layout outputs in tabs, rows, columns, and more._

**Run apps.** Run your notebook as a web app, with Python
code hidden and
uneditable:

```bash
marimo run your_notebook.py
```

<img src="docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

_This app is deployed on [marimo cloud](https://marimo.io/cloud), our
platform for deploying marimo notebooks and supercharging them
with cloud resources._

**Execute as scripts.** marimo noteboooks can be executed as scripts at the
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

**GitHub Copilot.** The marimo editor natively supports [GitHub
Copilot](https://copilot.github.com/). Enable it via the settings menu in the
marimo editor.

**VS Code extension.** If you prefer VS Code over terminal, try our
[VS Code extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo).

## Learn more

marimo is easy to get started with, with lots of room for power users. In
addition to experimenting with code and models in a reproducible environment,
marimo lets you build powerful tools including data labelers,
embedding visualizers, and model evaluation dashboards, with surprisingly
little code.

Examples are available in the `examples/` directory.
We've deployed many of these examples at our [public
gallery](https://marimo.io/@public); try them out!


Ready to learn more? Check out our [docs](https://docs.marimo.io/guides/overview.html)!

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
