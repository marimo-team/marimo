<p align="center" style="margin-top: 40px; margin-bottom: 40px;">
  <img src="_static/marimo-logotype-thick.svg" width="210px">
</p>

**marimo** is a reactive notebook for Python that models notebooks as dataflow
graphs. Run a cell or interact with a UI element, and marimo automatically runs
affected cells (or [marks them as stale](/guides/reactivity.md#runtime-configuration)),
keeping code and outputs consistent and preventing bugs before they happen.
Every marimo notebook is stored as pure Python, executable as a script, and
deployable as an app.

```{admonition} Built from the ground up
:class: tip

marimo was built from the ground up to solve <a
href="/faq.html#faq-jupyter">well-known problems associated with traditional
notebooks</a>.
```

::::{tab-set}
:::{tab-item} install with pip

```bash
pip install marimo && marimo tutorial intro
```

:::
:::{tab-item} install with uv

```bash
uv pip install marimo && marimo tutorial intro
```

:::
:::{tab-item} install with conda

```bash
conda install -c conda-forge marimo && marimo tutorial intro
```

:::
::::

Developer experience is core to marimo, with an emphasis on
reproducibility, maintainability, composability, and shareability.

**Highlights**.

- 🚀 **batteries-included:** replaces `jupyter`, `streamlit`, `jupytext`, `ipywidgets`, `papermill`, & more
- ⚡️ **reactive**: run a cell, and marimo reactively [runs all dependent cells](https://docs.marimo.io/guides/reactivity.html) or <a href="#expensive-notebooks">marks them as stale</a>
- 🖐️ **interactive:** [bind sliders, tables, plots, and more](https://docs.marimo.io/guides/interactivity.html) to Python — no callbacks required
- 🔬 **reproducible:** [no hidden state](https://docs.marimo.io/guides/reactivity.html#no-hidden-state), deterministic execution, [built-in package management](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **executable:** [execute as a Python script](https://docs.marimo.io/guides/scripts.html), parametrized by CLI args
- 🛜 **shareable**: [deploy as an interactive web app](https://docs.marimo.io/guides/apps.html) or [slides](https://docs.marimo.io/guides/apps.html#slides-layout), [run in the browser via WASM](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **designed for data**: query dataframes and databases [with SQL](https://docs.marimo.io/guides/sql.html), filter and search [dataframes](https://docs.marimo.io/guides/dataframes.html#displaying-dataframes)
- 🐍 **git-friendly:** notebooks are stored as `.py` files
- ⌨️ **a modern editor**: [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot), [AI assistants](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama), vim keybindings, variable explorer, and [more](https://docs.marimo.io/guides/editor_features/index.html)

> ⚡ marimo notebooks run automatically with interactions and code changes

<div align="center">
<figure>
<img src="/_static/readme-ui.gif"/>
</figure>
</div>

> ✨ express yourself with markdown, LaTeX, tables, accordions, tabs, grids, and more

<div align="center">
<figure>
<img src="/_static/outputs.gif"/>
</figure>
</div>

> 🔬 do reproducible science in an environment that makes your data tangible

<div align="center">
<figure>
<img src="/_static/faq-marimo-ui.gif"/>
</figure>
</div>

> 🚀 deploy as interactive web apps

<div align="center">
<figure>
<img src="/_static/docs-intro-app.gif"/>
</figure>
</div>

<h3>Contents</h3>

```{eval-rst}
.. toctree::
   :maxdepth: 2

   getting_started/index
   guides/index
   recipes
   api/index
   faq
   examples
   integrations/index
   community
```

```{eval-rst}
.. toctree::
   :caption: Links
   :maxdepth: 2

   GitHub <https://github.com/marimo-team/marimo>
   Discord <https://discord.gg/JE7nhX6mD8>
   Newsletter <https://marimo.io/newsletter>
   Twitter <https://twitter.com/marimo_io>
   Marimo Cloud Waitlist <https://marimo.io/cloud>
   Blog <https://marimo.io/blog>
```

<h3>Index</h3>

```{eval-rst}
* :ref:`genindex`
```
