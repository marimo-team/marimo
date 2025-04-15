# Importing Functions and Classes Defined in Marimo Notebooks

marimo's clean, intuitive Python file format allows you to define reusable functions and classes that can be imported directly into other Python scripts or notebooks, making your code more modular and reusable.

## Define Reusable Functions & Classes

You can define functions and classes that are directly accessible when importing your notebook as a Python module:

/// marimo-embed
```python
@app.function
def my_utility_function(x):
    return x * 2

@app.class_definition
class DataProcessor:
    def __init__(self, data):
        self.data = data

    def process(self):
        return [x * 2 for x in self.data]
```
///

then in another script/notebook

```python
from my_notebook import my_utility_function, DataProcessor
```

## Benefits of Reusable Functions

- **Import Directly**: Use functions from notebooks in other Python files
- **Clean Organization**: Keep your code modular and well-structured
- **Testing Support**: Easily test your notebook functions with [pytest](testing/pytest.md)
- **IDE Support**: Full linting and type checking support in your favorite editor

## How to Create Reusable Functions

### 1. Set up a Setup Cell

First, add a setup cell to your notebook for imports and constants that your functions will need:

```python
import pandas as pd
import numpy as np

DEFAULT_VALUE = 100
```

To add a setup cell in the editor, use the General menu and select "Add setup cell" (💠).

### 2. Define Your Function

Write a normal function/ class in a cell. A marker in the bottom right will
indicate that it is a reusable function.

!!! attention
    Functions can only reference imports and constants defined in the setup
    cell. If a function cannot be made reusable, the marker in the bottom right
    will provide a description why.

/// marimo-embed
```python
with app.setup:
    import pandas as pd
    import numpy as np

    DEFAULT_VALUE = 100

@app.function
def calculate_statistics(data):
    """Calculate basic statistics for a dataset"""
    return {
        "mean": np.mean(data),
        "median": np.median(data),
        "std": np.std(data)
    }
```
///

### 3. Reuse your definitions

Now you can import your function in other notebooks or Python scripts:

```python
# In another_script.py
from my_notebook import calculate_statistics

data = [1, 2, 3, 4, 5]
stats = calculate_statistics(data)
print(stats)
```

## Class Definitions

You can also define reusable classes with the `@app.class_definition` decorator:

```python
@app.class_definition
class DataProcessor:
    def __init__(self, data):
        self.data = data

    def normalize(self):
        return (self.data - np.mean(self.data)) / np.std(self.data)
```

## Best Practices

- Use setup cells for immediate, widely used imports (refrain from declaring constants, as import only blocks get an internal speedup)
- Keep function dependencies limited to setup cell references, or other top level declarations.
- Use descriptive names for your functions
- Add docstrings to document your functions' behavior

!!! tip | Functions can reference other functions defined with `@app.function`


## Limitations

- Functions cannot depend on variables defined in regular cells
- Like other cells, cyclic dependencies between functions are not allowed

## Looking for More?

For more detailed information about marimo's file format and features, check
out our [documentation on using your own
editor](https://docs.marimo.io/guides/editor_features/watching/) or view our
[File Format Tutorial](https://marimo.app/?slug=8n55fd).
