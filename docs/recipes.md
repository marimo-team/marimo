# Recipes

This page includes code snippets or "**recipes**" for a variety of common tasks:
use them as building blocks or examples when making your own notebooks.

_In the recipes, **each code block represents a cell**._
 
## Show an output conditionally

**Task.** Only show an output if a condition is `True`.

**Recipe.**

1. Use an `if` expression to choose which output to show.

```python
# condition is a boolean, True of False
condition = True
"condition is True" if condition else None
```

## Create a list of UI elements 

**Task.** Create a list of UI elements that react to user interactions.

**Recipe.**

1. Import packages.

```python
import marimo as mo
```

2. Use [`mo.ui.array`](api/inputs/array.md#marimo.ui.array) to group together
   many UI elements into a list.

```python
array = mo.ui.array([mo.ui.text(label=str(i)) for i in range(10)])
array
```

3. Get the value of the UI elements using `array.value`

```python
array.value
```
## Create a dictionary of UI elements 

**Task.** Create a dictionary of UI elements that react to user interactions.

**Recipe.**

1. Import packages.

```python
import marimo as mo
```

2. Use [`mo.ui.dictionary`](api/inputs/dictionary.md#marimo.ui.dictionary) to
   group together many UI elements into a list.

```python
dictionary = mo.ui.dictionary({i: mo.ui.text() for i in range(10)})
dictionary
```

3. Get the value of the UI elements using `dictionary.value`

```python
dictionary.value
```

## Reveal an output when a button is pressed

**Task.** 

**Recipe.**

```python
import marimo as mo
import random
```

```python
button = mo.ui.button(value=0, on_click=lambda count: count + 1)
button
```

```python
mo.md("#" + "🍃" * random.randint(1, 10)) if button.value > 0 else None
```

## Run code each time a buton is pressed

**Task.** 

**Recipe.**

```python
import marimo as mo
import random
```

```python
button = mo.ui.button(value=0, on_click=lambda count: count + 1)
button
```

```python
if button.value > 0:
  print(f"The button was pressed {button.value} times!")
```

## Run a cell on a timer

**Task.** Schedule a cell to run at a specified refresh rate. You can achieve
this with [`mo.ui.refresh`](api/inputs/refresh.md#marimo.ui.refresh).

**Recipe.** 3 cells:

1. Import packages
```python
import marimo as mo
import random
```

2. Create a refresh timer that fires once a second and output it:

```python
refresh = mo.ui.refresh(default_interval="1s")
# This outputs a timer that fires once a second
refresh
```

3. Reference the timer by name to make this cell run once a second

```python
# This cell will run once a second!
refresh

mo.md("#" + "🍃" * random.randint(1, 10))
```


