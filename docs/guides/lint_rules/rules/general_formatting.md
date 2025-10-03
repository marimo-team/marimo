# MF001: general-formatting

✨ **Formatting** 🛠️ Fixable

MF001: General formatting issues with the notebook format.

## What it does

Examines the notebook serialization for structural violations such as:
- Missing or incorrect marimo import statements
- Improperly formatted cell definitions
- Missing app initialization code
- Incorrect file generation metadata

## Why is this bad?

Format violations can prevent marimo from properly loading or executing
notebooks. While these don't affect the Python code logic, formatting errors
mark a deviation in the expected script structure, which can lead to
unexpected behavior when run as a script, or when loading the notebook.

## Examples

**Problematic:**
```python
# Missing marimo import
@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
```

**Solution:**
```python
import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __():
    return


if __name__ == "__main__":
    app.run()
```

**Note:** Most format issues are automatically fixable with `marimo check --fix`.

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [File Format Documentation](https://docs.marimo.io/guides/coming_from/jupyter/#marimo-file-format)

