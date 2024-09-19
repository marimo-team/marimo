# Coming from Streamlit

If you're familiar with Streamlit and looking to transition to marimo, this guide will help you understand how to achieve similar functionality in marimo. While both tools aim to simplify the creation of data apps, they have different approaches and philosophies.

## Key Differences

1. **Notebook vs. App Framework**: marimo is primarily a reactive notebook environment, while Streamlit is an app framework. marimo notebooks can be run as apps, but they're designed with a notebook-first approach.

2. **Execution Model**: marimo uses a reactive execution model where cells automatically update based on dependencies. Streamlit reruns the entire script on each interaction.

3. **File Format**: marimo notebooks and Streamlit apps are pure Python files (.py). However, marimo's structure allows for more fine-grained reactivity.

4. **UI Elements**: Both offer UI elements, but marimo's are more tightly integrated with the notebook environment. marimo also support the [anywidget](https://anywidget.dev/) spec for custom UI components.

5. **Built-in Editor**: marimo includes a built-in editor for notebooks, while Streamlit relies on external editors. Both approaches have their pros and cons.

6. **Iterative Development**: marimo's notebook environment allows for more interactive development and exploration, while Streamlit is more focused on building standalone apps.

## Common Streamlit Features in marimo

### 1. Displaying Text and Markdown

Streamlit:

```python
st.write("Hello World")
st.header("# Header")
```

marimo:

```python
import marimo as mo

mo.md("Hello World")
mo.md("# Header")
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
mo.md(f"Your age: {age}") # marimo can achieve more advanced composition
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

# In another cell
if button.value:
    mo.output.replace(mo.md("Button clicked!"))

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
mo.expander("Expand me", content=mo.md("Hello from the expander!"))
```

marimo's unique approach to composition allows for more flexible layouts with unlimited nesting.

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
fig, ax = plt.subplots()
ax.plot([1, 2, 3, 4])
fig  # Last expression is displayed
```

### 7. Caching

Streamlit:

```python
@st.cache_data
def expensive_computation():
    # ...
```

marimo:

```python
@functools.cache
def expensive_computation():
    # ...
```

### 8. Session State

Streamlit uses `st.session_state` for persisting data. In marimo, you can use regular Python variables, as the notebook maintains consistent state for cells that are not re-executed.

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

1. In marimo, cells are automatically re-executed when their dependencies change. But only the affected cells are re-executed, making it efficient.
2. UI elements in marimo are typically assigned to variables and their values accessed via the `value` attribute.
3. marimo's `mo.md()` function is versatile and can include both text and UI elements.
4. marimo's notebook-first approach allows for more exploratory data analysis and interactive development.
