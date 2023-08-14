# Best Practices

The few constraints marimo puts on your notebooks are natural consequences of
the fact that marimo programs are directed acyclic graphs. As long as you keep
this fact in mind, you'll quickly adapt to the marimo way of writing notebooks
and apps. You'll also find yourself writing better, more reproducible code.

Follow these tips to stay on the marimo way:

**Use global variables sparingly.** Keep the number of global variables in your
program small to avoid name collisions.

**Use descriptive names.** Use descriptive variable names, especially for
global variables. This will help you minimize name clashes, and will also
result in better code.

**Use functions.**
Encapsulate logic into functions to avoid polluting the global namespace with
temporary or intermediate variables, and to avoid code duplication.

**Use Python modules.** If your notebook gets too long, split complex logic
into helper Python modules and import them into your notebook.

**Minimize mutations.** marimo does not track mutations to objects. Try to
only mutate an object in the cell that creates it, or create new objects
instead of mutating existing ones.

**Write idempotent cells.** Write cells whose outputs and behavior are the same
when given the same inputs (references); such cells are called idempotent. This
will help you avoid bugs and cache expensive intermediate computations.

**Cache computations with `@functools.cache`.** Use Python's builtin
`functools` library to cache expensive computations.

For example,

```python
import functools

@functools.cache
def compute_predictions(problem_parameters):
	...
```

Whenever `compute_predictions` is called with a value of `problem_parameters`
it has not seen, it will compute the predictions and store them in a cache. The
next time it is called with the same parameters, instead of recomputing the
predictions, it will return the previously computed value from the cache.
