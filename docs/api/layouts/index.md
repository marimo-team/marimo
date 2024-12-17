# Layouts

marimo has higher-order layout functions that you can use to arrange outputs
in rows, columns, tables, tabs, and more.

## Stateless

Unlike elements in `marimo.ui`, these don't have any values associated with
them but just render their children in a certain way.

| Function | Description |
|----------|-------------|
| [`marimo.accordion`](accordion.md) | Create collapsible sections |
| [`marimo.carousel`](carousel.md) | Create a slideshow |
| [`marimo.callout`](callout.md) | Create highlighted sections |
| [`marimo.center`](center.md) | Center content |
| [`marimo.hstack`](hstack.md) | Stack elements horizontally |
| [`marimo.lazy`](lazy.md) | Lazy load content |
| [`marimo.left`](left.md) | Left-align content |
| [`marimo.nav_menu`](nav_menu.md) | Create navigation menus |
| [`marimo.plain`](plain.md) | Display content without styling |
| [`marimo.right`](right.md) | Right-align content |
| [`marimo.routes`](routes.md) | Create page routing |
| [`marimo.sidebar`](sidebar.md) | Create sidebars |
| [`marimo.tree`](tree.md) | Create tree structures |
| [`marimo.vstack`](vstack.md) | Stack elements vertically |

## Stateful

Some elements in `marimo.ui` are also helpful for layout. These elements
do have values associated with them: for example, `tabs` tracks the
selected tab name, and `table` tracks the selected rows.

| Function | Description |
|----------|-------------|
| [`marimo.ui.tabs`](../inputs/tabs.md) | Create tabbed interfaces |
| [`marimo.ui.table`](../inputs/table.md) | Create interactive tables |
