# Importing Functions and Classes Defined in Marimo Notebooks

You can import top-level functions and classes defined in a marimo notebook
into other Python scripts or notebooks using normal Python syntax, as long as
your definitions satisfy the simple criteria described on this page. This makes
your notebook code modular and reusable, testable, and easier to edit in text editors
of your choice.

## Overview

For a function or class to be saved at the top level of the notebook file, it must 
meet the following **criteria**:

1. The cell must define just a single function or class.
2. The defined function or class can only refer to symbols defined in the
   [setup cell](#create-a-setup-cell), or to other top-level symbols.


### Example

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

In another script or notebook

```python
from my_notebook import my_utility_function, DataProcessor
```

## Creating a top-level function

### 1. Create a setup cell

First, add a **setup cell** to your notebook for imports that your functions or
classes will need:

```python
import numpy as np
```

To add a setup cell in the editor, use the General menu and select "Add setup cell" (💠).

Setup cells are guaranteed to run before all other cells.

### 2. Define your function

Define a single function in a cell. If the
[criteria](overview) for top-level
functions are met, a marker in the bottom right will indicate that it is a
reusable function.

!!! note

    Functions can only reference symbols defined in the setup cell. If a
    function cannot be serialized top-level, the marker in the
    bottom right will provide a description why.

/// marimo-embed
```python
with app.setup:
    import numpy as np

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

Under the hood, marimo decorates top-level functions with `@app.function`,
which you can use to define your own top-level functions if you are editing a
notebook file directly.

### 3. Reuse your definitions

Now you can import your function in other notebooks or Python scripts:

```python
# In another_script.py
from my_notebook import calculate_statistics

data = [1, 2, 3, 4, 5]
stats = calculate_statistics(data)
print(stats)
```

## Class definitions

Classes are also serialized top-level if they meet the [criteria](overview).
Under the hood, marimo decorates top-level classes with
`@app.class_definition`, which you can use if you are editing your notebook
file directly:

```python
@app.class_definition
class DataProcessor:
    def __init__(self, data):
        self.data = data

    def normalize(self):
        return (self.data - np.mean(self.data)) / np.std(self.data)
```

## Best practices

- Use setup cells for immediate, widely used imports
- Keep function dependencies limited to setup-cell references, or other top-level declarations.
- Use descriptive names for your functions
- Add docstrings to document your functions' behavior

!!! tip 

    Top-level symbols can reference other top-level symbols.


## Limitations

- Functions cannot depend on variables defined in regular cells
- Like other cells, cyclic dependencies between functions are not allowed

## Learn more

For more detailed information about marimo's file format and features, check
out our [documentation on using your own
editor](https://docs.marimo.io/guides/editor_features/watching/) or view our
[file format tutorial](https://marimo.app/?slug=8n55fd).
