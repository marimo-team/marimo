# JupyterHub

> For full documentation, visit the
> [marimo-jupyter-extension repository](https://github.com/marimo-team/marimo-jupyter-extension).

The [marimo JupyterLab extension](https://github.com/marimo-team/marimo-jupyter-extension)
integrates marimo into JupyterLab and JupyterHub, letting you launch
marimo notebooks directly from JupyterLab's launcher, manage running sessions,
and convert Jupyter notebooks to marimo format.

<figure>
  <img src="/_static/docs-jupyterhub.png" alt="marimo JupyterLab extension showing sidebar and editor" />
  <figcaption>marimo running in a JupyterHub deployment, in JupyterLab.</figcaption>
</figure>

## Features

- **Launcher integration**: marimo appears in the JupyterLab launcher with its own icon
- **First-class notebook support**: double-click `_mo.py` files to open directly in marimo
- **Sidebar panel**: monitor server status, view running sessions with kill buttons, and access quick actions
- **Environment selection**: choose from available Python environments when creating notebooks; the extension discovers Jupyter kernel specs, letting you use your own venvs or conda environments.
- **Context menus**: right-click `.py` files to edit with marimo, or `.ipynb` files to convert to marimo format
- **Sandbox mode**: run marimo in isolated environments with `uvx`

### File type handling

| File Type | Double-click | Right-click |
|-----------|-------------|-------------|
| `_mo.py`  | Opens in marimo | "Edit with marimo" |
| `.py`     | Opens in standard editor | "Edit with marimo" |
| `.ipynb`  | Opens in Jupyter | "Convert to marimo" |

## Installation

### Single environment

```bash
uv pip install 'marimo[sandbox]>=0.19.11' marimo-jupyter-extension
```

### JupyterHub (multiple environments)

| Package | Install location | Why |
|---------|-----------------|-----|
| `marimo` | User's environment | Access user's packages |
| `marimo-jupyter-extension` | Jupyter's environment | Jupyter must import it |

## Configuration

Configure the extension in `jupyterhub_config.py`:

```python
# Explicit marimo path
c.MarimoProxyConfig.marimo_path = "/opt/bin/marimo"

# Or use uvx mode (sandbox)
c.MarimoProxyConfig.uvx_path = "/usr/local/bin/uvx"

# Startup timeout (default: 60s)
c.MarimoProxyConfig.timeout = 120
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| marimo icon missing | Install `marimo-jupyter-extension` in Jupyter's environment |
| marimo fails to launch | Ensure marimo is in PATH or configure `MarimoProxyConfig.marimo_path` |
| Modules not found | Install marimo in the same environment as your packages |
| Sandbox features not working | Upgrade to `marimo[sandbox]>=0.19.11` |

For more troubleshooting tips, see the
[full documentation](https://github.com/marimo-team/marimo-jupyter-extension).
