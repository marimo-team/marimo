# MR001: self-import

⚠️ **Runtime** ❌ Not Fixable

MR001: Importing a module with the same name as the file.

## What it does

Analyzes import statements in each cell to detect cases where the imported
module name matches the current file's name (without the .py extension).

## Why is this bad?

Importing a module with the same name as the file causes several issues:
- Python may attempt to import the current file instead of the intended module
- This can lead to circular import errors or unexpected behavior
- It makes the code confusing and hard to debug
- It can prevent the notebook from running correctly

This is a runtime issue because it can cause import confusion and unexpected behavior.

## Examples

**Problematic (in a file named `requests.py`):**
```python
import requests  # Error: conflicts with file name
```

**Problematic (in a file named `math.py`):**
```python
from math import sqrt  # Error: conflicts with file name
```

**Solution:**
```python
# Rename the file to something else, like my_requests.py
import requests  # Now this works correctly
```

**Alternative Solution:**
```python
# Use a different approach that doesn't conflict
import urllib.request  # Use alternative library
```

## References

- [Understanding Errors](https://docs.marimo.io/guides/understanding_errors/)
- [Python Import System](https://docs.python.org/3/reference/import.html)

