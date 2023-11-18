# Recipes

This page includes code snippets or "**recipes**" for a variety of common tasks.
Use them as building blocks or examples when making your own notebooks.

In these recipes, **each code block represents a cell**.
 
## Control Flow

### Show an output conditionally

**Task.** Only show an output if a condition is `True`.

**Recipe.**

1. Use an `if` expression to choose which output to show.

```python
# condition is a boolean, True of False
condition = True
"condition is True" if condition else None
```

### Run a cell on a timer

**Task.** Schedule a cell to run at a specified refresh rate. You can achieve
this with [`mo.ui.refresh`](api/inputs/refresh.md#marimo.ui.refresh).

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Create a refresh timer that fires once a second:

```python
refresh = mo.ui.refresh(default_interval="1s")
# This outputs a timer that fires once a second
refresh
```

3. Reference the timer by name to make this cell run once a second

```python
import random

# This cell will run once a second!
refresh

mo.md("#" + "🍃" * random.randint(1, 10))
```

### Require form submission before sending UI value

**Task.** Wait for submission of a form before sending UI element values
to the backend.

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Create a submittable form.

```python
form = mo.text(label="Your name").form()
form
```

3. Get the value of the form.

```python
form.value
```

### Stop execution of a cell and its children

**Task.** Stop execution of a cell and its children if a condition is met. For
example, don't run a cell if a form is unsubmitted.

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Create a submittable form.

```python
form = mo.text(label="Your name").form()
form
```

3. Use [`mo.stop`](api/control_flow.md#marimo.stop) to stop execution when
the form is unsubmitted.

```python
mo.stop(form.value is None, mo.md("Submit the form to continue"))

mo.md(f"Hello, {form.value}!")
```


## Grouping UI elements together
### Create a list of UI elements 

**Task.** Create a list of UI elements that reacts to user interactions,
especially when the number of elements is not known until runtime.

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

### Create a dictionary of UI elements 

**Task.** Create a dictionary of UI elements that reacts to user interactions,
especially when the number of elements is not known until runtime.

**Recipe.**

1. Import packages.

```python
import marimo as mo
```

2. Use [`mo.ui.dictionary`](api/inputs/dictionary.md#marimo.ui.dictionary) to
   group together many UI elements into a list.

```python
dictionary = mo.ui.dictionary({str(i): mo.ui.text() for i in range(10)})
dictionary
```

3. Get the value of the UI elements using `dictionary.value`

```python
dictionary.value
```

### Create a form with multiple UI elements

**Task.** Batch multiple UI elements into a submittable form.

**Recipe.**

1. Import packages.

```python
import marimo as mo
```

2. Use [`mo.ui.form`](api/inputs/form.md#marimo.ui.form) and
[`Html.batch`](api/Html.md#marimo.Html.batch) to create a form with
multiple elements.

```python
form = mo.md(
   r"""
   Choose your algorithm parameters:

   - $\lambda$: {lmbda}
   - $\rho$: {rho}
   """
).batch(lmbda=mo.ui.slider(0.1, 1, step=0.1), rho=mo.ui.number(1, 10)).form()
form
```

3. Get the submitted form value.

```python
form.value
```


## Working with buttons

### Create a counter button

**Task.** Create a button that counts the number of times it's clicked.

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Use [`mo.ui.button`](api/inputs/button.md#marimo.ui.button) and its
   `on_click` argument to create a counter button.

```python
# Initialize the button value to 0, increment it on every click
button = mo.ui.button(value=0, on_click=lambda count: count + 1)
button
```

3. Get the button value

```python
button.value
```

### Create a toggle button

**Task.** Create a button that toggles between `True` and `False`. (Tip: you
can also just use [`mo.ui.switch`](api/inputs/switch.md#marimo.ui.switch).)

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Use [`mo.ui.button`](api/inputs/button.md#marimo.ui.button) and its
   `on_click` argument to create a toggle button.

```python
# Initialize the button value to False, flip its value on every click.
button = mo.ui.button(value=False, on_click=lambda value: not value)
button
```

3. Get the button value.

```python
button.value
```

### Reveal an output when a button is pressed

**Task.** Reveal an output when a button is pressed.

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Create a counter button.

```python
button = mo.ui.button(value=0, on_click=lambda count: count + 1)
button
```

3. Show an output after the button is clicked.

```python
mo.md("#" + "🍃" * button.value) if button.value > 0 else None
```

### Run a cell when a buton is pressed

**Task.** Conditionally run a code each time a button is pressed.

**Recipe.**

1. Import packages

```python
import marimo as mo
```

2. Create a counter button.

```python
# on_click takes the current value of the button and returns a new value
button = mo.ui.button(value=0, on_click=lambda count: count + 1)
button
```

3. Run code every time the button is clicked.

```python
if button.value > 0:
  print(f"The button was pressed {button.value} times!")
```
