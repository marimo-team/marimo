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

```python
pip install marimo && marimo tutorial intro
```

![marimo](docs/_static/docs-intro.gif)

When you run a cell, marimo _automatically_ runs all other cells that depend on
it (like a spreadsheet!). This **reactivity**, along with marimo's built-in
**interactive** UI elements, lets you make powerful notebooks and apps that _make
your data tangible_. 

**Highlights.**

- **reactive**: run a cell, and marimo automatically runs cells that depend on it
- **interactive**: connect inputs like sliders, dropdowns, plots, and
  more to Python
- **expressive**: write dynamic makdown parametrized by UI elements, plots, or anything else
- **Pythonic**: no callbacks, no magical syntax — just Python
- **git-friendly**: notebooks stored as `.py` files


## Quickstart

**Installation.** In a terminal, run

```bash
pip install marimo
marimo tutorial intro
```

You should see a tutorial notebook in your browser.

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
unified platform for deploying and sharing notebooks and apps._


**Automatically convert Jupyter notebooks.** Automatically translate Jupyter notebooks to marimo notebooks:

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

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

marimo is easy to get started with, with lots of room for power users.
You can build powerful apps, including data labeling tools, embedding
visualizers, model evaluation dashboards, and more,  with surprisingly little
code.

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
- 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
- 💬 [Join us on Discord](https://discord.gg/JE7nhX6mD8)
- 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
- 🕴️ [Follow us on LinkedIn](https://www.linkedin.com/company/marimo-io)
- ✏️  [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
