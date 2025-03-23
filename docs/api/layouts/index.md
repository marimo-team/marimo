# Layouts

marimo has higher-order layout functions that you can use to arrange outputs
in rows, columns, tables, tabs, and more.

## Stateless

Unlike elements in `marimo.ui`, these don't have any values associated with
them but just render their children in a certain way.

| Function | Description |
|----------|-------------|
| [`marimo.accordion`][marimo.accordion] | Create collapsible sections |
| [`marimo.carousel`][marimo.carousel] | Create a slideshow |
| [`marimo.callout`][marimo.callout] | Create highlighted sections |
| [`marimo.center`][marimo.center] | Center content |
| [`marimo.hstack`][marimo.hstack] | Stack elements horizontally |
| [`marimo.lazy`][marimo.lazy] | Lazy load content |
| [`marimo.left`][marimo.left] | Left-align content |
| [`marimo.nav_menu`][marimo.nav_menu] | Create navigation menus |
| [`marimo.plain`][marimo.plain] | Display content without styling |
| [`marimo.right`][marimo.right] | Right-align content |
| [`marimo.routes`][marimo.routes] | Create page routing |
| [`marimo.sidebar`][marimo.sidebar] | Create sidebars |
| [`marimo.tree`][marimo.tree] | Create tree structures |
| [`marimo.json`][marimo.json] | Create JSON structures |
| [`marimo.vstack`][marimo.vstack] | Stack elements vertically |

## Stateful

Some elements in `marimo.ui` are also helpful for layout. These elements
do have values associated with them: for example, `tabs` tracks the
selected tab name, and `table` tracks the selected rows.

| Function | Description |
|----------|-------------|
| [`marimo.ui.tabs`][marimo.ui.tabs] | Create tabbed interfaces |
| [`marimo.ui.table`][marimo.ui.table] | Create interactive tables |
