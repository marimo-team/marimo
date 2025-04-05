# Star imports

You're probably on this page because you just saw an error like this one:

<div align="center">
<figure>
<img src="/_static/docs_import_star_error.png" width="700px"/>
</figure>
</div>

marimo raises this error you attempt to use `import *`.

In this example, `x` was already defined, and the subsequent cell raised an
error when we tried to run it. In your case, perhaps your variable is a loop
variable (`i`), a dataframe (`df`), or a plot (`fig`, `ax`).

## Why can't I use `*` imports?

Star imports are incompatible with marimo's git-friendly file format and reproducible reactive execution:

- marimo's Python file format stores code in functions, so notebooks can be imported as regular Python modules without executing all their code. But Python disallows `import *` everywhere except at the top-level of a module.
- Star imports would also silently add names to globals, which would be
incompatible with [reactive execution](../reactivity.md).

Even Python's [official style guide](https://peps.python.org/pep-0008/) discourages the use of `import *`, writing:

> Wildcard imports (from <module> import *) should be avoided, as they make it unclear which names are present in the namespace, confusing both readers and many automated tools. 

**What do I get in return?**
By accepting this constraint on imports, marimo makes your notebooks:

- **reproducible**, with a well-defined execution order, no hidden state, and no hidden bugs;
- **executable** as a script;
- **interactive** with UI elements that work without callbacks;
- **shareable as a web app**, with far better performance that streamlit.

As a bonus, you'll find that you end up with cleaner, reusable code.

## How do I fix this error?

Fixing this error is simple: just import the module, and use `.` notation
to access its members.

```python
import math

math.pi
```

instead of

```
from math import *

pi
```
