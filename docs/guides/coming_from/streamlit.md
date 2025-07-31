# Coming from Streamlit

If you're familiar with Streamlit and looking to transition to marimo, read on.

The biggest difference between Streamlit and marimo is that
Streamlit can only be used for data apps, whereas marimo is a notebook-first
programming environment that makes it effortless to run notebooks as apps.
In addition, marimo is much more performant than streamlit.

## Key Differences

1. **Notebook vs. App Framework**:
   - marimo is primarily a reactive notebook
   environment,  while Streamlit is an app framework.
   - marimo notebooks can be run as apps -- often with better performance
   than streamlit apps -- but they're designed with a notebook-first approach.
   - When creating streamlit apps, it is common to first prototype them as Jupyter
   notebooks, then migrate and refactor them into streamlit apps. With marimo,
   every notebook is automatically an app; there's no migration step needed.

2. **Performance.**
   - marimo uses a reactive execution model that, on interaction or code
     change, runs the minimal subset of notebook code needed to keep your
     notebook up-to-date.
   - Streamlit reruns the entire script on each interaction, which frequently
     causes performance issues.

3. **File Format**:
    - marimo notebooks and Streamlit apps are pure Python files (.py).
    - marimo's structure allows for more fine-grained reactivity.
    - Unlike streamlit files, marimo files can be executed as Python scripts from the
      command-line, and can be imported and used as a module by other Python
      programs. For example, other programs can [reuse cells][marimo.Cell.run] from
      a marimo notebook.

4. **UI Elements**:

- Both offer UI elements like sliders, text fields, and tables.
- In streamlit,
creating a UI element automatically outputs it to the display.
 -In marimo, the
creation of a UI element is separated from its display, meaning that you can
easily create custom layouts and higher-order elements, and even emit the same UI element twice.
- marimo support the [anywidget](https://anywidget.dev/) spec for custom UI components, letting
you reuse widgets that were originally developed for the Jupyter ecosystem,
- streamlit has its own system for creating custom components.

5. **Built-in Editor**:

- marimo includes a [built-in editor](../editor_features/index.md) for notebooks, designed specifically
for working with data.
- Streamlit relies on external editors.
- Both approaches have their pros and cons.

6. **Working with data.**:

- marimo's notebook environment allows for iterative and interactive
  development and exploration, letting it serve as your daily driver for
  working with data. marimo even has native support for [SQL](../working_with_data/sql.md).
- Streamlit is exclusively used for building standalone data apps.

## Common Streamlit Features in marimo

### 1. Displaying text

Streamlit:

```python
import streamlit as st
st.markdown(
    """
    # Greetings
    Hello world
    """
)
```

marimo:

```python
import marimo as mo
mo.md(
    """
    # Greetings
    Hello world
    """
)
```

### 2. Displaying Data

Streamlit:

```python
st.dataframe(df)
```

marimo:

```python
df  # Last expression in a cell is automatically displayed
```

### 3. Input Widgets

Streamlit:

```python
age = st.slider("How old are you?", 0, 130, 25)
```

marimo:

```python
age = mo.ui.slider(label="How old are you?", start=0, stop=130, value=25)
mo.md(f"One more question: {age}") # marimo can achieve more advanced composition
```

### 4. Buttons

Streamlit:

```python
if st.button("Click me"):
    st.write("Button clicked!")
```

marimo:

```python
button = mo.ui.run_button("Click me")
```

```python
# In another cell
if button.value:
    mo.output.replace(mo.md("Button clicked!"))
```

```
# Or
mo.md("Button clicked!") if button.value else None
```

### 5. Layouts

Streamlit:

```python
col1, col2 = st.columns(2)
with col1:
    st.write("Column 1")
with col2:
    st.write("Column 2")
```

marimo:

```python
mo.hstack([
    mo.md("Column 1"),
    mo.md("Column 2")
])
```

### 6. Advanced Layouts (tabs, accordions)

Streamlit:

```python
with st.expander("Expand me"):
    st.write("Hello from the expander!")
```

marimo:

```python
mo.accordion({"Expand me": "Hello from the expander!"})
```

marimo's unique approach to composition allows for more flexible layouts with
unlimited nesting.

### 6. Plotting

Streamlit:

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot([1, 2, 3, 4])
st.pyplot(fig)
```

marimo:

```python
import matplotlib.pyplot as plt

plt.plot([1, 2, 3, 4])
plt.gca()  # Last expression is displayed
```

### 7. Caching

Streamlit:

```python
@st.cache_data
def expensive_computation(args):
    # ...
```

marimo:

```python
@mo.cache
def expensive_computation(args):
    # ...
```

marimo provides [`mo.cache`](../../api/caching.md/#marimo.cache) and [`mo.lru_cache`](../../api/caching.md/#marimo.lru_cache) for caching function return values, as well as [`mo.persistent_cache`](../../api/caching.md/#marimo.persistent_cache) for caching variables to disk.

### 8. Session State

Streamlit uses `st.session_state` for persisting data. In marimo, you can use
regular Python variables, as the notebook maintains consistent state for cells
that are not re-executed.

### 9. Running as an App

Streamlit:

```bash
streamlit run your_app.py
```

marimo:

```bash
marimo run your_notebook.py
```

## Key Concepts to Remember

1. In marimo, cells are automatically re-executed when their dependencies change. But only the affected cells are re-executed, making it far more efficient than a naively written streamlit program.
2. UI elements in marimo are typically assigned to variables and their values accessed via the `value` attribute.
3. marimo's `mo.md()` function is versatile and can include both text and UI elements with f-strings.
4. marimo's notebook-first approach allows it to be used for all kinds of data work, including exploratory data analysis, data engineering, machine learning experimentation and model training, library documentation and examples, and more.
