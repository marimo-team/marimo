<p align="center" style="margin-top: 40px; margin-bottom: 40px;">
  <img src="_static/marimo-logotype-thick.svg" width="210px">
</p>

**marimo** is a reactive notebook for Python. It allows you to rapidly experiment
with data and models, code with confidence in your notebook's correctness, and
productionize notebooks as pipelines or interactive web apps.

::::{tab-set}
:::{tab-item} install with pip

```bash
pip install marimo && marimo tutorial intro
```

:::
:::{tab-item} install with conda

```bash
conda install -c conda-forge marimo && marimo tutorial intro
```

:::
::::

**Highlights.**

- **reactive**: run a cell, and marimo automatically updates all affected cells and outputs
- **interactive**: bind sliders, tables, plots, and more to Python — no callbacks required
- **reproducible**: no hidden state, deterministic execution order
- **deployable**: executable as a script, deployable as an app
- **developer-friendly**: git-friendly `.py` file format, GitHub Copilot, fast autocomplete, code formatting, and more

_marimo was built from the ground up to solve many <a
href="/faq.html#faq-jupyter">well-known problems associated with traditional
notebooks_</a>.

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

> 🚀 deploy your creations as interactive web apps

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

<h3>Index</h3>

```{eval-rst}
* :ref:`genindex`
```
