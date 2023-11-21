# Best practices

Here are best practices for writing marimo notebooks.

**Use global variables sparingly.** Keep the number of global variables in your
program small to avoid name collisions. If you have intermediate variables,
encapsulate them in functions or prefix them with an underscore (`_tmp = ...`) to
make them local to a cell.

**Use descriptive names.** Use descriptive variable names, especially for
global variables. This will help you minimize name clashes, and will also
result in better code.

**Use functions.** Encapsulate logic into functions to avoid polluting the
global namespace with
temporary or intermediate variables, and to avoid code duplication.

**Use Python modules.** If your notebook gets too long, split complex logic
into helper Python modules and import them into your notebook.

**Minimize mutations.** marimo does not track mutations to objects. Try to
only mutate an object in the cell that creates it, or create new objects
instead of mutating existing ones.

:::{dropdown} Example

_Don't_ split up declarations and mutations over multiple cells. For example, _don't
do this:_

```python
l = [1, 2, 3]
```

```python
l.append(new_item())
```

Instead, _do_ **declare and mutate in the same cell**:

```python
l = [1, 2, 3]
...
l.append(new_item())
```

or, if working in multiple cells, **declare a new variable based on the old
one**:

```python
l = [1, 2, 3]
```

```python
extended_list = l + [new_item()]
```
:::



**Write idempotent cells.**
Write cells whose outputs and behavior are the same
when given the same inputs (references); such cells are called idempotent. This
will help you avoid bugs and cache expensive intermediate computations.

**Cache computations with `@functools.cache`.**
Use Python's builtin `functools` library to cache expensive computations.

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
