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

**marimo** es un cuaderno (notebook) de Python: ejecuta una celda o interactúa con un elemento de la interfaz de usuario y marimo ejecuta automáticamente las celdas dependientes (o <a href="#expensive-notebooks">las marca como desactualizadas</a>), manteniendo el código y los resultados consistentes. Los cuadernos (notebooks) de marimo se almacenan como código Python puro, ejecutables como scripts y desplegables como aplicaciones.

**Puntos Destacados**.

- 🚀 **baterías incluidas:** reemplaza `jupyter`, `streamlit`, `jupytext`, `ipywidgets`, `papermill` y más
- ⚡️ **reactive**: ejecuta una celda y marimo reactivamente [ejecuta las celdas dependientes](https://docs.marimo.io/guides/reactivity.html) o <a href="#expensive-notebooks">las marca como desactualizadas</a>
- 🖐️ **interaction:** [vincula deslizadores, tablas, gráficas y más](https://docs.marimo.io/guides/interactivity.html) a Python — sin "callbacks" requeridos
- 🔬 **reproducible:** [sin estado oculto](https://docs.marimo.io/guides/reactivity.html#no-hidden-state), ejecución determinística, [gestión de paquetes integrada](https://docs.marimo.io/guides/editor_features/package_management.html)
- 🏃 **ejecutable:** [se ejecuta como script de Python](https://docs.marimo.io/guides/scripts.html), parametrizable mediante argumentos de la línea de comandos (CLI)
- 🛜 **compartible**: [se despliega como una aplicación web interactiva](https://docs.marimo.io/guides/apps.html) o [diapositivas](https://docs.marimo.io/guides/apps.html#slides-layout), [ejecutar en navegador via WASM](https://docs.marimo.io/guides/wasm.html)
- 🛢️ **diseñado para datos**: consulta marcos de datos y bases de datos [con SQL](https://docs.marimo.io/guides/working_with_data/sql.html), filtrar y buscar [marcos de datos](https://docs.marimo.io/guides/working_with_data/dataframes.html)
- 🐍 **compatible con git:** cuadernos (notebooks) son almacenados como archivos `.py`
- ⌨️ **un editor moderno**: [GitHub Copilot](https://docs.marimo.io/guides/editor_features/ai_completion.html#github-copilot), [asistentes IA](https://docs.marimo.io/guides/editor_features/ai_completion.html#using-ollama), atajos de teclado de vim, explorador de variables y [más](https://docs.marimo.io/guides/editor_features/index.html)

```python
pip install marimo && marimo tutorial intro
```

_¡Prueba marimo en [nuestro entorno de pruebas](https://marimo.app/l/c7h6pz), se ejecuta completamente en el navegador!_

_[Inicia rápido](#quickstart) para una introducción sobre nuestro CLI._

## Un entorno de programación reactivo

marimo garantiza que el código de tu notebook, los resultados y el estado del programa sean consistentes. Esto [resuelve muchos problemas](https://docs.marimo.io/faq.html#faq-problems) asociados con notebooks tradicionales como Jupyter.

**Un entorno de programación reactivo.**
Ejecuta una celda y marimo reacciona ejecutando automáticamente las celdas que referencian sus variables, eliminando la tarea propensa a errores de volver a ejecutar celdas manualmente. Elimina una celda y marimo borra sus variables de la memoria del programa, eliminando el estado oculto.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/reactive.gif" width="700px" />

<a name="expensive-notebooks"></a>

**Compatible con cuadernos (notebooks) pesados.** marimo te permite [configurar el runtime
para que sea
lazy](https://docs.marimo.io/guides/configuration/runtime_configuration.html),
marcando las celdas afectadas como obsoletas en lugar de ejecutarlas automáticamente. Esto te da garantías sobre el estado del programa mientras previene la ejecución accidental de celdas costosas.

**Elementos UI sincronizados.** Interactúa con [
elementos UI](https://docs.marimo.io/guides/interactivity.html) como [sliders](https://docs.marimo.io/api/inputs/slider.html#slider),
[dropdowns](https://docs.marimo.io/api/inputs/dropdown.html), [transformadores de dataframes](https://docs.marimo.io/api/inputs/dataframe.html), e [
interfaces de chat](https://docs.marimo.io/api/inputs/chat.html), y las celdas que los usan se vuelven a ejecutar automáticamente con sus valores más recientes.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-ui.gif" width="700px" />

**Marcos de datos interactivos.** [Navega, busca, filtra, y 
ordena](https://docs.marimo.io/guides/working_with_data/dataframes.html)
millones de filas increíblemente rápido, sin necesidad de codigo.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-df.gif" width="700px" />

**Tiempo de ejecución eficiente.** marimo ejecuta solo las celdas que necesitan ser ejecutadas analizando estáticamente tu código.

**Markdown dinámico y SQL.** Usa markdown para contar historias dinámicas que dependen de
datos de Python. O construye consultas [SQL](https://docs.marimo.io/guides/working_with_data/sql.html) 
que dependen de valores de Python y ejecútalas contra dataframes, bases de datos, CSVs, Google Sheets, o cualquier otra cosa usando nuestro motor SQL integrado, que devuelve el resultado como un dataframe de Python.

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/readme-sql-cell.png" width="700px" />

Tus notebooks siguen siendo Python puro, incluso si usan markdown o SQL.

**Orden de ejecución determinístico.** Los notebooks se ejecutan en un orden determinístico, basado en referencias de variables en lugar de las posiciones de las celdas en la página.
Organiza tus notebooks para que se ajusten mejor a las historias que quieres contar.

**Gestión de paquetes integrada.** marimo tiene soporte integrado para todos los gestores de paquetes principales, permitiéndote [instalar paquetes al importarlos](https://docs.marimo.io/guides/editor_features/package_management.html). marimo puede incluso 
[serializar los requisitos de paquetes](https://docs.marimo.io/guides/package_management/inlining_dependencies/)
en archivos de notebook, e instalarlos automáticamente en sandboxes venv aislados.

**Baterías incluidas.** marimo viene con GitHub Copilot, asistentes de IA, formateo de código con Ruff, exportación HTML, autocompletado rápido, una [extensión de VS Code](https://marketplace.visualstudio.com/items?itemName=marimo-team.vscode-marimo),
un visor interactivo de dataframes, y [muchas más](https://docs.marimo.io/guides/editor_features/index.html)
características de calidad de vida.

## Inicio rápido

**Instalación.** En una terminal, ejecuta

```bash
pip install marimo  # or conda install -c conda-forge marimo
marimo tutorial intro
```

Para instalar con dependencias adicionales que desbloquean celdas SQL, completado con IA y más, ejecuta

```bash
pip install marimo[recommended]
```

**Crear cuadernos (notebooks).**

Crea o edita notebooks con

```bash
marimo edit
```

**Ejecutar aplicaciones.**  Ejecuta tu notebook como una aplicación web, con el código Python oculto y no editable:

```bash
marimo run your_notebook.py
```

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/docs-model-comparison.gif" style="border-radius: 8px" width="450px" />

**Ejecutar como scripts.** Ejecuta un notebook como un script en la línea de comandos:

```bash
python your_notebook.py
```

**Convertir cuadernos (notebooks) de Jupyter automáticamente.** Convierte automáticamente notebooks de Jupyter a notebooks de marimo con el CLI:

```bash
marimo convert your_notebook.ipynb > your_notebook.py
```

o usa nuestra [interfaz web](https://marimo.io/convert).

**Tutoriales.**
Lista de todos los tutoriales:

```bash
marimo tutorial --help
```

## ¿Preguntas?

Consulta las [FAQ](https://docs.marimo.io/faq.html) en nuestra documentacion.

## Aprende más

marimo es fácil para empezar, con mucho espacio para usuarios avanzados. Por ejemplo, aquí hay un visualizador de embeddings hecho en marimo
([video](https://marimo.io/videos/landing/full.mp4)):

<img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/embedding.gif" width="700px" />

Revisa nuestra [documentacion](https://docs.marimo.io),
la carpeta [`examples/`](examples/), y nuestra [galeria](https://marimo.io/gallery) para aprender mas.

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

¡Apreciamos todas las contribuciones! No necesitas ser un experto para ayudar. Por favor consulta [CONTRIBUTING.md](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) para más detalles sobre cómo empezar.

> Dudas? Acércate a nosotros [en Discord](https://marimo.io/discord?ref=readme).

## Comunidad

Estamos construyendo una comunidad. ¡Ven a pasar el rato con nosotros!

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

marimo es una **reinvención** de Python como un programa Python reproducible, interactivo y compartible, en lugar de un bloc de notas JSON propenso a errores.

Creemos que las herramientas que usamos dan forma a nuestra manera de pensar — mejores herramientas, para mentes mejores. Con marimo, esperamos proporcionar a la comunidad de Python un mejor entorno de programación para hacer investigación y comunicarla; para experimentar con código y compartirlo; para aprender ciencia computacional y enseñarla.

Nuestra inspiración viene de muchos lugares y proyectos, especialmente
[Pluto.jl](https://github.com/fonsp/Pluto.jl),
[ObservableHQ](https://observablehq.com/tutorials), y
[los ensayos de Bret Victor](http://worrydream.com/). marimo es parte de
un movimiento mayor hacia la programación reactiva de flujo de datos. Desde
[IPyflow](https://github.com/ipyflow/ipyflow), [streamlit](https://github.com/streamlit/streamlit),
[TensorFlow](https://github.com/tensorflow/tensorflow),
[PyTorch](https://github.com/pytorch/pytorch/tree/main),
[JAX](https://github.com/google/jax), y
[React](https://github.com/facebook/react), las ideas de programación funcional, declarativa y reactiva están transformando una amplia gama de herramientas para mejor.

<p align="right">
  <img src="https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-horizontal.png" height="200px">
</p>
