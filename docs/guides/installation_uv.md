
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

A pyproject.toml file makes it easier to manage your project’s dependencies in one place. Using the uv tool, you can quickly set up and customize your project’s environment

```bash
uv init           # Creates a pyproject.toml file
uv add marimo     # Adds "marimo>=0.9.31" to dependencies
uv run marimo edit hi.py
```


### Reading a `pyproject.toml` from an already exisiing project.
    

## Temporary installation
This won't create a virtual environment folder in your working direory. 
Instead, uv will cache all dependencies, make a temporary venv in your system, which will be destroyed after exiting the process.

```bash
uv tool run marimo edit hi.py
```
this line is 100% identical to 
```bash
uvx marimo edit hi.py
```
(`uvx` is an alias for `uv tool run`)


## From URL

This pattern will run marimo from a URL.


With uv run URL

What is the word 

I'm looking for a word to describe this kind of code pattern.
`pip install 
I can run a script like this
uv run https://gist.githubusercontent.com/kolibril13/f4597c16452b4b72965c8d20fe6c0978/raw/a7757d3f206d467f6e76eeea621e64b0cb92530c/benchmark.py
``` 


# globally installed tool

This is not recommended, as dependencies will be installed globally as well. #TODO:FactCheck

```
uv tool install marimo
```

Use a **specific python version** (this will overwrite the previous global installation):

```
UV_PYTHON=python3.11 uv tool install marimo 
```

**Update** global version of marimo:
```
uv tool install marimo --upgrade.
```

**Uninstall**
```
uv tool install marimo
```