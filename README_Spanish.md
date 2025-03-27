<p align="center">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg">
</p>

<p align="center">
  <em>Un cuaderno (notebook) de Python reactivo que es reproducible, compatible con Git y desplegable como scripts o aplicaciones.</em>

<p align="center">
  <a href="https://docs.marimo.io" target="_blank"><strong>Documentos</strong></a> ·
  <a href="https://marimo.io/discord?ref=readme" target="_blank"><strong>Discord</strong></a> ·
  <a href="https://github.com/marimo-team/marimo/tree/main/examples" target="_blank"><strong>Ejemplos</strong></a> ·
  <a href="https://www.youtube.com/@marimo-team/" target="_blank"><strong>YouTube</strong></a>
</p>

<p align="center">
  <b>Español | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README.md" target="_blank"><b>Inglés</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Chinese.md" target="_blank"><b>Chino</b></a>
  <b> | </b>
  <a href="https://github.com/marimo-team/marimo/blob/main/README_Japanese.md" target="_blank"><b>Japonés</b></a>
</p>

<p align="center">
<a href="https://pypi.org/project/marimo/"><img src="https://img.shields.io/pypi/v/marimo?color=%2334D058&label=pypi" /></a>
<a href="https://anaconda.org/conda-forge/marimo"><img src="https://img.shields.io/conda/vn/conda-forge/marimo.svg"/></a>
<a href="https://marimo.io/discord?ref=readme"><img src="https://shields.io/discord/1059888774789730424" alt="discord" /></a>
<img alt="Pepy Total Downloads" src="https://img.shields.io/pepy/dt/marimo?label=pypi%20%7C%20downloads"/>
<img alt="Conda Downloads" src="https://img.shields.io/conda/d/conda-forge/marimo" />
<a href="https://github.com/marimo-team/marimo/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/marimo" /></a>
</p>

**marimo** es un cuaderno (notebook) de Python: ejecuta una celda o interactúa con un elemento de la interfaz de ususario y marimo ejecuta automaticamente las celdas dependientes (o <a href="#expensive-notebooks">las marca como desactualizadas</a>), manteniendo el código y los resultados consistentes. Los cuadernos (notebooks) de marimo se almacenan como código Python puro, ejecutables como scripts y desplegables como aplicaciones.

**Puntos Destacados**.

- 🚀 **baterias incluidas:** reemplaza `jupyter`, `streamlit`, `jupytext`, `ipywidgets`, `papermill` y más
- ⚡️ **reactive**: ejecuta una celda y marimo reactivamente [ejecuta las celdas dependientes](https://docs.marimo.io/guides/reactivity.html) o <a href="#expensive-notebooks">las mara omo desactualizadas</a>
- 🖐️ **interaction:** [vincula deslizadores, tablas, gráficas y más](https://docs.marimo.io/guides/interactivity.html) a Python — sin "callbacks" requeridos
- 🔬 **reproducible:** [sin estado oculto](https://docs.marimo.io/guides/reactivity.html#no-hidden-state), ejecución determinística, [gestión de paquetes integrada](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **ejecutable:** [se ejecuta como script de Python](https://docs.marimo.io/guides/scripts.html), parametrizable mediante arguments de la línea de commandos (CLI)
- 🛜 **compartible**: [se depsliega como una aplicación web interactiva](https://docs.marimo.io/guides/apps.html) o [diapositivas](https://docs.marimo.io/guides/apps.html#slides-layout), [ejecutar en navegador via WASM](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **diseñado para datos**: consulta marcos de datos y bases de datos [con SQL](https://docs.marimo.io/guides/working_with_data/sql.html), filtrar y buscar [marcos de datos](https://docs.marimo.io/guides/working_with_data/dataframes.html)
- 🐍 **compatible con git:** cuadernos (notebooks) son almacenados como archivos `.py`
- ⌨️ **un editor moderno**: [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot), [asistentes IA](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama), atajos de teclado de vim, explorador de variables y [más](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_¡Prueba marimo en [nuestro entorno de pruebas](https://marimo.app/l/c7h6pz), se ejecuta completamente en el navegador!_

_[Inicia rápido](#quickstart) para una introducción sobre nuestro CLI._

## Un entorno de programación reactivo

marimo guarantees your notebook code, outputs, and program state are consistent. This [solves many problems](https://docs.marimo.io/faq.html#faq-problems) associated with traditional notebooks like Jupyter.

**Un entorno de programación reactivo.**
Run a cell and marimo _reacts_ by automatically running the cells that
reference its variables, eliminating the error-prone task of manually
re-running cells. Delete a cell and marimo scrubs its variables from program
memory, eliminating hidden state.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**Compatible con cuadernos (notebooks) pesados.** marimo lets you [configure the runtime
to be
lazy](https://docs.marimo.io/guides/configuration/runtime_configuration.html),
marking affected cells as stale instead of automatically running them. This
gives you guarantees on program state while preventing accidental execution of
expensive cells.

**Elementos UI sincronizados.** Interact with [UI
elements](https://docs.marimo.io/guides/interactivity.html) like [sliders](https://docs.marimo.io/api/inputs/slider.html#slider),
[dropdowns](https://docs.marimo.io/api/inputs/dropdown.html), [dataframe
transformers](https://docs.marimo.io/api/inputs/dataframe.html), and [chat
interfaces](https://docs.marimo.io/api/inputs/chat.html), and the cells that
use them are automatically re-run with their latest values.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**Marcos de datos interactivos.** [Page through, search, filter, and
sort](https://docs.marimo.io/guides/working_with_data/dataframes.html)
millions of rows blazingly fast, no code required.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**Tiempo de ejecución eficinte.** marimo runs only those cells that need to be run by
statically analyzing your code.

**Markdown dinámico y SQL.** Use markdown to tell dynamic stories that depend on
Python data. Or build [SQL](https://docs.marimo.io/guides/working_with_data/sql.html) queries
that depend on Python values and execute them against dataframes, databases,
CSVs, Google Sheets, or anything else using our built-in SQL engine, which
returns the result as a Python dataframe.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

Your notebooks are still pure Python, even if they use markdown or SQL.

**Orden de ejecución determinístico.** Notebooks are executed in a deterministic
order, based on variable references instead of cells' positions on the page.
Organize your notebooks to best fit the stories you'd like to tell.

**Gestión de paquetes integrado.** marimo has built-in support for all major
package managers, letting you [install packages on import](https://docs.marimo.io/guides/editor_features/package_management.html). marimo can even
[serialize package
requirements](https://docs.marimo.io/guides/package_reproducibility.html)
in notebook files, and auto install them in
isolated venv sandboxes.

**Baterias incluidas.** marimo comes with GitHub Copilot, AI assistants, Ruff
code formatting, HTML export, fast code completion, a [VS Code
extension](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo),
an interactive dataframe viewer, and [many more](https://docs.marimo.io/guides/editor_features/index.html)
quality-of-life features.

## Inicio rápido

**Instalación.** In a terminal, run

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

To install with additional dependencies that unlock SQL cells, AI completion, and more,
run

```bash
pip install marimo[recommended]
```

**Crear cuadernos (notebooks).**

Create or edit notebooks with

```bash
marimo edit
```

**Ejecutar aplicaciones.** Run your notebook as a web app, with Python
code hidden and uneditable:

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**Ejecutar como scripts.** Execute a notebook as a script at the
command line:

```bash
python your_notebook.py
```

**Convertir cuadernos (notebooks) de Jupyter automáticamente.** Automatically convert Jupyter
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

## ¿Preguntas?

See the [FAQ](https://docs.marimo.io/faq.html) at our docs.

## Aprende más

marimo is easy to get started with, with lots of room for power users.
For example, here's an embedding visualizer made in marimo
([video](https://marimo.io/videos/landing/full.mp4)):

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

Check out our [docs](https://docs.marimo.io),
the [`examples/`](examples/) folder, and our [gallery](https://marimo.io/gallery) to learn more.

<table border="0">
  <tr>
    <td>
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html">
        <img src="https://docs.marimo.io/_static/reactive.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html">
        <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" style="max-height: 150px; width: auto; display: block" />
      </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html">
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
      <a target="_blank" href="https://docs.marimo.io/getting_started/key_concepts.html"> Tutorial </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/api/inputs/index.html"> Inputs </a>
    </td>
    <td>
      <a target="_blank" href="https://docs.marimo.io/guides/working_with_data/plotting.html"> Plots </a>
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

## Contribuir

We appreciate all contributions! You don't need to be an expert to help out.
Please see [CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) for more details on how to get
started.

> Questions? Reach out to us [on Discord](https://marimo.io/discord?ref=readme).

## Comunidad

We're building a community. Come hang out with us!

- 🌟 [Star us on GitHub](https://github.com/marimo-team/marimo)
- 💬 [Chat with us on Discord](https://marimo.io/discord?ref=readme)
- 📧 [Subscribe to our Newsletter](https://marimo.io/newsletter)
- ☁️ [Join our Cloud Waitlist](https://marimo.io/cloud)
- ✏️ [Start a GitHub Discussion](https://github.com/marimo-team/marimo/discussions)
- 🦋 [Follow us on Bluesky](https://bsky.app/profile/marimo.io)
- 🐦 [Follow us on Twitter](https://twitter.com/marimo_io)
- 🎥 [Subscribe on YouTube](https://www.youtube.com/@marimo-team)
- 🕴️ [Follow us on LinkedIn](https://www.linkedin.com/company/marimo-io)

## Inspiración ✨

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
