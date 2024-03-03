# Layouts

```{eval-rst}
.. toctree::
  :maxdepth: 1
  :hidden:

  accordion
  callout
  justify
  stacks
  tree
```

marimo has higher-order layout functions that you can use to arrange outputs
in rows, columns, tables, tabs, and more.

## Stateless

Unlike elements in `marimo.ui`, these don't have any values associated with
them but just render their children in a certain way.

```{eval-rst}
.. autosummary::
  :nosignatures:

  marimo.accordion
  marimo.callout
  marimo.center
  marimo.hstack
  marimo.left
  marimo.right
  marimo.tree
  marimo.vstack
```

## Stateful

Some elements in `marimo.ui` are also helpful for layout. These elements
do have values associated with them: for example, `tabs` tracks the
selected tab name, and `table` tracks the selected rows.

```{eval-rst}
.. autosummary::
  :nosignatures:

  marimo.ui.tabs
  marimo.ui.table
```
