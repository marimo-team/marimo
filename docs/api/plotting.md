# Plotting

marimo supports all major plotting libraries, including matplotlib, seaborn,
plotly, and altair. Just import your plotting library of choice and use it
as you normally would.

```{admonition} Reactive plots coming soon!
:class: admonition

We're working on a way to let you select data in a plot with your mouse, and
have your selection automatically passed to Python — stay tuned!
```

**Tip: outputting matplotlib plots.**
To output a matplotlib plot in a cell's output area, include its `Axes` or
`Figure` object as the last expression in your notebook. For example:

```python
plt.plot([1, 2])
# plt.gca() gets the current `Axes`
plt.gca()
```

or

```python
fig, ax = plt.subplots()

ax.plot([1, 2])
ax
```

If you want to output the plot in the console area, use `plt.show()` or
`fig.show()`.

```{eval-rst}
.. autofunction:: marimo.mpl.interactive
```
