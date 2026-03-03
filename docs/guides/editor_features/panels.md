# Sidebar and Developer Panel

marimo organizes editor tools into two main areas: the **sidebar** on the left and the **developer panel** at the bottom. This layout keeps everyday notebook tools easily accessible while providing a dedicated space for debugging and development utilities.

<div align="center">
<picture>
  <source srcset="/_static/docs-sidebar-developer-panel.webp" type="image/webp">
  <img src="/_static/docs-sidebar-developer-panel.jpg" alt="Editor showing sidebar on the left and developer panel at the bottom" style="max-width: 700px; width: 100%;" />
</picture>
</div>

## Sidebar

The sidebar provides quick access to panels you'll use frequently while working on notebooks. Click the icons on the left edge of the editor to open panels.

**Default sidebar panels:**

| Panel | Description |
|-------|-------------|
| **Files** | Browse workspace files and [inspect remote storage connections](../working_with_data/remote_storage.md) |
| **Variables** | Explore variables and data sources in your notebook |
| **Packages** | View installed packages and manage dependencies |
| **AI** | Chat with AI assistants and use agents |
| **Outline** | Navigate your notebook via table of contents |
| **Documentation** | View live documentation as you type |
| **Dependencies** | Visualize cell relationships with the minimap and dependency graph |

Toggle the sidebar with `Cmd/Ctrl-Shift-S`.

## Developer Panel

The developer panel houses tools for debugging, tracing execution, and other advanced functionality. It appears at the bottom of the editor, similar to the developer tools in VS Code or browser DevTools.

**Default developer panel tabs:**

| Panel | Description |
|-------|-------------|
| **Errors** | View all errors across your notebook |
| **Scratchpad** | A scratch cell for quick experiments without affecting your notebook |
| **Tracing** | Monitor cell execution and performance |
| **Secrets** | Manage environment secrets |
| **Logs** | View stdout and stderr output |
| **Terminal** | Integrated terminal for shell commands |
| **Snippets** | Browse and insert code snippets |

Toggle the developer panel with `Cmd/Ctrl-J`.

<!-- TODO: Add screenshot of developer panel expanded -->

## Customizing your layout

Both the sidebar and developer panel are fully customizable. You can:

- **Reorder panels**: Drag panels to rearrange their order within a section
- **Move panels between sections**: Drag a panel from the sidebar to the developer panel (or vice versa) to relocate it
- **Hide panels**: Right-click a panel icon to access options for hiding or moving it

Your layout preferences are saved and persist across sessions. Panels automatically adapt their appearance based on their location — showing a more compact vertical layout in the sidebar and a wider horizontal layout in the developer panel.

<div align="center">
<video autoplay muted loop playsinline style="max-width: 700px; width: 100%; border-radius: 8px;">
  <source src="/_static/docs-panel-drag-drop.webm" type="video/webm">
</video>
</div>

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl-J` | Toggle developer panel |
| `Cmd/Ctrl-Shift-S` | Toggle sidebar |
| `Cmd/Ctrl-Shift-I` | Open minimap (in Dependencies panel) |
| `` Ctrl-` `` | Open terminal |
