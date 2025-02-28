# Snippets Configuration

marimo provides a snippets feature that allows you to quickly insert commonly used code blocks into your notebooks. You can configure both the default snippets and add your own custom snippets.

## Configuration Options

You can configure snippets through your `.marimo.toml` file:

```toml
[snippets]
custom_paths = ["/path/to/your/snippets/dir"]  # List of paths to directories containing custom snippets
include_default_snippets = true  # Whether to include marimo's default snippets (defaults to true)
```

## Custom Snippets

To add your own snippets:

1. Create a directory to store your snippets
2. Add the directory path to the `custom_paths` list in your configuration
3. Create snippet files in your directory following the marimo snippet format

### Snippet Format

Snippets are Python files that follow a specific format. Each snippet should be a marimo notebook file with a title and code:

Example snippet file (`my_snippet.py`):

```python
import marimo

app = marimo.App(width="medium")

@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Load .env""")
    return


@app.cell
def _():
    import dotenv

    dotenv.load_dotenv(dotenv.find_dotenv(usecwd=True))
    return (dotenv,)


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
```

## Default Snippets

marimo comes with a set of default snippets for common operations. You can disable the default snippets by setting `include_default_snippets = false` in your configuration.
