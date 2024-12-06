
# Installation with uv

There are four methods to run a Marimo notebook using UV:
1.	Within a project environment
2.	Temporary installation (cached)
3.	Directly from a URL
4.	Using UV as a globally installed tool


# Project evnironment

We recommend using marimo in a project environment like this:
```py
uv venv
uv pip install marimo
uv run marimo edit hi.py
```

Note: this venv can also be activated via `source .venv/bin/activate` and then marimo can be started via `marimo edit hi.py`, but this pattern is **not recommended**.  

For specific python versions, use `uv venv --python 3.13`.
The default python version is defined at #TODO CHECK.

There are 3 ways to install packages.

a) Terminal: `pip install matplotlib polars`
b) In the notebook itself type `import polars as pd` and a installation guide will pop up.
c) Go to the packages tab, and select the package.

#Todo: screen recroding of packages tab.

If you want to define your project dependencies in `pyproject.toml`, you can make the following workflow:

```
uv init (this will create a pyproject.toml file)
uv add marimo  (this will add "marimo>=0.9.9" to dependencies in pyproject.toml)
uv run marimo edit hi.py 
```

# Temporary installation
This won't create a virtual environment folder in your working direory. 
Instead, uv will cache all dependencies, make a temporary venv in your system, which will be destroyed after exiting the process.

`
uv tool run marimo edit hi.py
`
this line is 100% identical to 
`
uvx marimo edit hi.py
`



# From URL

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