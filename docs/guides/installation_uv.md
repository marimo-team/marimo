
# Running Marimo with `uv`

You can run a Marimo notebook using `uv` through one of the following methods:

1. **Within a project environment**  
2. **Temporary installation (cached)**  
3. **Directly from a URL**  
4. **Using `uv` as a globally installed tool**

---

## Running in a Project Environment

We recommend running Marimo within a project-specific environment.  
Here's how you can set it up:

```bash
uv venv
uv pip install marimo
uv run marimo edit hi.py
```

The `uv run` command provides the simplest way to access the virtual environment.   

However, if you prefer to activate it manually, you can do so with the following commands:

```bash
source .venv/bin/activate
marimo edit hi.py
``` 

---
### Using Specific Python Versions

To specify a Python version, add the `--python` option while creating the venv. For example:

```bash
uv venv --python 3.13
```

```{admonition} Tip
:class: tip

uv will automatically fetch Python versions as needed — you don't need to install Python to get started.
```
<!-- Source: https://docs.astral.sh/uv/guides/install-python/#installing-python -->


If no version is specified, the default Python version is used (currently: **[TODO: Specify default Python version]**).

---

### Installing Packages

There are three ways to install additional packages:

1. **Via Terminal**  
   Run the following command:  
   ```bash
   uv pip install matplotlib polars
   ```

2. **Within the Notebook**  
   Type `import polars as pd`. Run the cell, and a "Missing package" pop up window will appear.

<div align="center">
<figure>
<img src="/_static/image.png" width="650px"/>
<figcaption>
Screenshot demonstrating the "Missing package" window.
</figcaption>
</figure>
</div>


1. **Using the Packages Tab**  
   Navigate to the "Packages" tab and select the desired package.

<div align="center">
<figure>
<img src="/_static/image-1.png" width="400px"/>
<figcaption>
Screenshot demonstrating the "Packages" tab.
</figcaption>
</figure>
</div>


### Defining Dependencies with `pyproject.toml`

A pyproject.toml file makes it easier to manage your project’s dependencies in one place. Using `uv`, you can quickly set up and customize your project’s environment

```bash
uv init           # Creates a pyproject.toml file
uv add marimo     # Adds "marimo>=0.9.31" to dependencies
uv run marimo edit hi.py
```


### Reading a `pyproject.toml` from an Existing Project

If you already have a `pyproject.toml` file—for example, when cloning an existing project—you can use the `uv sync` command to synchronize and install the dependencies defined within it:

```bash
uv sync
uv run marimo edit hi.py

```



This command ensures that your environment matches the dependency specifications of the existing project, making it simple to get up and running without manually adding packages.    


## Temporary Installation

When you execute a command using `uv tool run`, no virtual environment folder is created in your working directory. Instead, `uv` takes the following steps:

1. **Caches dependencies or reuses existing cached ones** based on the metadata in the Marimo notebook.
2. **Creates a temporary virtual environment** on your system.
3. **Deletes the temporary environment** immediately after the process ends.

This lightweight approach keeps your workspace clean while still providing an isolated, dependency-managed environment for running commands.

For instance, you can run:

```bash
uv tool run marimo edit hi.py
```

During the session, you can install additional packages, but their information will not be preserved once the session ends. This is where notebook metadata comes into play, as explained in the following section.

---

### Specifying Additional Requirements

To include dependency information to the metadata, use the --sandbox option:

```bash
uv tool run marimo edit hi.py --sandbox
```

While working in the notebook, you can install packages through pop-ups or via the **Packages** tab. However, **adding packages through the terminal is not supported in sandbox mode.** *(#TODO: Fact-check this limitation.)*

---

### Fully Self-Contained Notebooks

A unique feature of this setup is that the notebook becomes **fully self-contained** and reproducible by anyone. This is achieved by embedding package metadata directly within the notebook, following the guidelines of [PEP 723 – Inline Script Metadata](https://peps.python.org/pep-0723/). 

When opened in a plain text editor, the notebook displays the following embedded metadata: *(#TODO: Replace this example with a screenshot from a text editor.)*

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "polars==1.16.0",
# ]
# ///

import marimo

__generated_with = "0.9.31"
app = marimo.App(width="medium")


@app.cell
def __():
    import polars
    return (polars,)
```

Once the session ends, the venv is cleared.  
To reconstruct the session, simply run:

```bash
uv tool run marimo edit hi.py --sandbox
```

Marimo detects the embedded dependencies in sandbox mode, so you can also use:

```bash
uv tool run marimo edit hi.py
```

In this case, the Marimo CLI will show:

```bash
Run in a sandboxed venv containing this notebook's dependencies? 
[Y/n]
```

---

### Simplifying with `uvx`

For convenience, `uvx` is a shorthand for `uv tool run`. These two commands are equivalent:

```bash
uv tool run marimo edit hi.py
uvx marimo edit hi.py
```
## From URL

This pattern will run marimo from a URL.


With uv run URL

What is the word 

I'm looking for a word to describe this kind of code pattern.
`pip install 
I can run a script like this
uv run https://gist.githubusercontent.com/kolibril13/f4597c16452b4b72965c8d20fe6c0978/raw/a7757d3f206d467f6e76eeea621e64b0cb92530c/benchmark.py



# Globally Installed Tool

It is generally **not recommended** to install tools globally, as dependencies will also be installed globally. *(#TODO: Fact-check this recommendation.)*

### Installation

To install the tool globally, use:

```bash
uv tool install marimo
```

### Using a Specific Python Version

To install the tool globally with a specific Python version, use the following command. This will overwrite any existing global installation:

```bash
UV_PYTHON=python3.11 uv tool install marimo
```

### Updating the Global Version

To update the global version of Marimo, run:

```bash
uv tool install marimo --upgrade
```

### Uninstallation

To uninstall the globally installed tool, use:

```bash
uv tool uninstall marimo
```