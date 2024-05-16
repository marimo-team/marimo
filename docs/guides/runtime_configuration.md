# Runtime configuration

Through the notebook settings menu, you can configure how and when marimo
runs cells.

## On startup

By default, marimo runs notebooks automatically on startup. Disable
this by unchecking "Autorun on startup".

_When sharing a notebook as an app with `marimo run`, this setting has
no effect._

## On cell change

By default, when a cell is run or a UI element is interacted with, marimo
automatically runs cells that reference any of its variables. **You can disable
automatic execution of cell's descendants in the notebook settings menu by
setting `"On cell change"` to `"lazy"`.**

When the runtime is lazy, running a cell marks affected cells as stale but
doesn't automatically run them. Lazy evaluation means cells are only run when
their outputs are needed. If you run a cell that has stale ancestors, those
ancestors will also run to make sure your cell doesn't use stale inputs. You
can always click the notebook run button or use the keyboard shortcut to run
all stale cells.

**When should I use lazy evaluation?** Choosing the lazy runtime can be helpful
when working on notebooks with expensive cells.

_When sharing a notebook as an app with `marimo run`, this setting has
no effect._

## On module change

Enable module autoreloading via the settings icon (top right). When enabled,
when Python modules that your notebook imports are modified, marimo reloads
those modifications so you can use the latest version of your code. This works
recursively, meaning that marimo tracks modifications for modules imported
by your notebook's imported modules too.

Autoreloading comes in two types:

- "lazy": automatically marks cells affected by module
  modifications as stale, letting you know which cells need to be re-run.
- "autorun": automatically re-runs cells affected by module modification.

**Why autoreload?** Autoreloading enables a workflow that many developers find
productive: develop complex logic in Python modules, and use the marimo
notebook as a DAG or main script that orchestrates your logic.
