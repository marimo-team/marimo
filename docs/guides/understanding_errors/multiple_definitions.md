# Multiple definitions

You're probably on this page because you just saw an error like this one:

<div align="center">
<figure>
<img src="/_static/docs_redefines_variables_error.png" width="700px"/>
</figure>
</div>

marimo raises this error when a variable is defined in multiple cells. In
this example, `x` was already defined, and the subsequent cell raised
an error when we tried to run it. In your case, perhaps your variable
is a loop variable (`i`), a dataframe (`df`), or a plot (`fig`, `ax`).

??? Tip "Watch our YouTube explainer"

    <div align="center">
    <iframe width="700" height="393" src="https://www.youtube.com/embed/5TzAADGRfxU?si=ZtwQoAzEUL2UABNq" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
    </div>

## Why can't I redefine variables?

**Understanding the error message.** The error message tells you which other
cells defined the multiply defined variable. You can click on the cell name,
and marimo will highlight it.

**Why can't I redefine variables?** marimo guarantees that the code on the page
matches the outputs you see by determining a deterministic execution order on
cells; when one cell runs, marimo knows which others should run. But if two
cells defined `x`, and a third showed `x`, the output of the third cell would
be ambiguous, depending on which of the defining cells ran first (should it be
`0` or `1`?). That's a problem because it creates [hidden state and hidden
bugs](../coming_from/jupyter.md), and it's part of the reason why [over 96% of
Jupyter notebooks on GitHub aren't reproducible](https://leomurta.github.io/papers/pimentel2019a.pdf).

**What do I get in return?**

By accepting this constraint on variables, marimo makes your notebooks:

- **reproducible**, with a well-defined execution order, no hidden state, and no hidden bugs;
- **executable** as a script;
- **interactive** with UI elements that work without callbacks;
- **shareable as a web app**, with far better performance than streamlit.

As a bonus, you'll find that you end up with cleaner, reusable code.

## How do I fix this error?

You have a few options.

### Use local variables

In marimo, variables prefixed with an underscore (`_x` or `_i`) are made local
to a cell, and can be redefined across multiple cells.

```python
for _i in range(10):
    ...
```

Use this in a pinch, but prefer encapsulating code in functions.

### Encapsulate code in a function

Python provides local scope through functions: if the variable that was
redefined is meant to be a temporary variable, then you can make it local to
the cell by encapsulating the code in a function. If any of the cell's
variables are not meant to be local, or are outputs meant to be displayed, just
return them from the function.

In general, we recommend writing modular code with meaningful functions. But,
in a pinch, just declare an anonymous function like this one to get a "local scope":


```python
def _():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([1, 2])
    return ax

_() 
```

That's what clicking on the "Fix: Wrap in a function" button does. Note the function
`_()` is local to the cell.


### Merge cells

Often you can simply merge the cells that define the same variable into a single cell.
To incrementally show outputs in the cell, use [`mo.output.append`][marimo.output.append]
or `print()`.

### Chain dataframe methods

When working with dataframes, instead of splitting up operations across
multiple cells, chain operations in a single cell. This is especially ergonomic
when using [Polars](https://docs.pola.rs/), Daft, or other modern dataframe
libraries that support lazy execution.
