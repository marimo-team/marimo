# Understanding dataflow

Unlike traditional notebooks, marimo understands the relationships between
cells and uses this information to keep your code and outputs consistent. These
relationships are represented as a **dataflow graph**, which encodes how
variables flow from one cell to another.

The dataflow graph, which is inferred statically from variable definitions and
references, is used to automatically run (or mark stale) cells in the correct
sequence; it's also why cells can be arranged "out of order" on the page, or
across columns.

marimo provides several tools to help you visualize and understand the
relationships it identifies between cells.

## Variables explorer

The **variables explorer panel** collects marimo's understanding of the
variables in your notebook into a single searchable list. 

<div align="center">
<picture>
  <source srcset="/_static/docs-variables-panel.webp" type="image/webp">
  <img src="/_static/docs-variables-panel.jpg" alt="Variables panel showing variable relationships" style="max-width: 700px; width: 100%;" />
</picture>
</div>

To open the panel, click the **variables icon** in the **left sidebar panel**.
The variable explorer shows each variable's name, type, value, where it's
defined, and where it's used.

## Dependency explorer

The **dependency explorer panel** provides a _bird's-eye view_ of your
notebook's dataflow, showing all cells as an interactive graph. It helps you
understand high-level patterns, overall connectedness, and the broader
structure of your notebook.

<div align="center">
<picture>
  <source srcset="/_static/docs-dependency-explorer.webp" type="image/webp">
  <img src="/_static/docs-dependency-explorer.jpg" alt="Dependency explorer showing a graph view of cell connections" style="max-width: 700px; width: 100%;" />
</picture>
</div>

To open the dependency explorer, click the **graph icon** in the **left sidebar
panel**. You can choose between vertical or horizontal layouts.

## Minimap

The **minimap** provides a _focused slice_ of your notebook's dataflow, helping
you understand the reactive context of a given cell and navigate related cells.
You can toggle the minimap a _hotkey_ (`Cmd/Ctrl-Shift-i`), or select the **map
icon** from the **footer toolbar**.

Click a cell in the minimap to jump to it:

<div align="center">
<video autoplay muted loop playsinline style="max-width: 700px; width: 100%;">
  <source src="/_static/docs-minimap.webm" type="video/webm">
  <source src="/_static/docs-minimap.mp4" type="video/mp4">
</video>
</div>

Connections are read **left to right**:

- Connections to the **left** are _direct inputs_ — cells the current cell reads from
- Connections to the **right** are _direct outputs_ — cells that read from the current cell
- Cells positioned left or right but not directly connected are _transitive
dependencies_ — cells that influence or are influenced by the current cell, but
only through one or more intermediate cells

The minimap can take some getting used to, but it's an effective representation
for understanding how data flows around the current cell. It's meant to show
_just enough_ local context to help you debug, trace relationships, and
navigate complex notebooks. For a high level overview, use the [dependency
explorer](#dependency-explorer).

### Cell symbols

The minimap uses visual indicators to show the status and connectivity of each cell:

<table tabindex="0">
  <thead>
    <tr>
      <th>Symbol</th>
      <th>Meaning</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <svg viewBox="-8 -8 16 16" width="16">
          <circle r="3"></circle>
          <path d="M 0 0 H -6" stroke-width="2" stroke="black">
          </path>
        </svg>
      </td>
      <td>Cell uses variables from other cells</td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-8 -8 16 16" width="16">
          <circle r="3"></circle>
          <path d="M 0 0 H 6" stroke-width="2" stroke="black">
          </path>
        </svg>
      </td>
      <td>Cell defines variables used by other cells</td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-8 -8 16 16" width="16">
          <circle r="3"></circle>
          <path d="M 0 0 H -6" stroke-width="2" stroke="black">
          </path>
          <path d="M 0 0 H 6" stroke-width="2" stroke="black">
          </path>
        </svg>
      </td>
      <td>
        Cell uses variables <i>and</i> defines variables used by others
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-8 -8 16 16" width="16">
          <circle r="3"></circle>
        </svg>
      </td>
      <td>
        Cell defines variables but isn't connected to anything (safe to delete)
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-8 -8 16 16" width="16">
          <circle r="1.5" fill="#c4c4c4"></circle>
        </svg>
      </td>
      <td>
        Cell doesn't define or use variables from other cells (often markdown)
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-8 -8 16 16" width="16">
          <circle r="3" fill="#ff6565"></circle>
        </svg>
      </td>
      <td>Cell has an error</td>
    </tr>
  </tbody>
</table>


### Reading cell connections

When you select a cell, the minimap draws lines showing how data flows between
cells. Since marimo cells can define multiple variables, downstream connections
show all cells that reference any variable from your selected cell.

<table tabindex="0">
  <thead>
    <tr>
      <th>Path</th>
      <th>Interpretation</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>
        <svg viewBox="-18 -8 36 32" width="36" style="color: #0780e9">
          <circle r="3" fill="currentColor"></circle>
          <path d="M 0 0 H 7 V 21 H 14" fill="none" stroke-width="2" stroke="currentColor"></path>
          <circle r="3" cx="14" cy="21" fill="currentColor" ></circle>
        </svg>
      </td>
      <td>
        First cell defines variables used by the second cell. Second cell will
        re-run when the first runs
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-18 -8 36 32" width="36" style="color: #0780e9">
          <circle r="3" fill="currentColor"></circle>
          <path d="M 0 0 H -7 V 21 H -14" fill="none" stroke-width="2" stroke="currentColor"></path>
          <circle r="3" cx="-14" cy="21" fill="currentColor"></circle>
        </svg>
      </td>
      <td>
        First cell uses variables from the second cell. First cell will re-run
        when the second runs
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-18 -8 36 56" width="36" style="color: #0780e9">
          <circle r="3" fill="currentColor"></circle>
          <path d="M 0 0 H 7 V 21 H 14" fill="none" stroke-width="2" stroke="currentColor"></path>
          <circle r="3" cx="14" cy="21" fill="currentColor"></circle>
          <circle r="3" cy="42" fill="#c4c4c4"></circle>
        </svg>
      </td>
      <td>
        Gray cell has no connection to the blue cells above
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-18 -8 36 56" width="36" style="color: #0780e9; overflow: visible">
          <circle r="3" fill="currentColor"></circle>
          <path d="M 0 0 H 7 V 21 H 20" fill="none" stroke-width="2" stroke="currentColor"></path>
          <circle r="3" cx="14" cy="21" fill="currentColor"></circle>
          <path d="M 14 42 H 8" fill="none" stroke-width="2" stroke="#c4c4c4"></path>
          <circle r="3" cx="14" cy="42" fill="#c4c4c4"></circle>
        </svg>
      </td>
      <td>
        Gray cell indirectly uses variables from the first cell. Whiskers
        indicate transitive dependencies
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-18 -8 36 56" width="36" style="color: #0780e9; overflow: visible">
          <circle r="3" cx="-14" fill="currentColor"></circle>
          <path d="M -20 0 H -7 V 21 H 0" fill="none" stroke-width="2" stroke="currentColor"></path>
          <circle r="3" cy="21" fill="currentColor"></circle>
          <path d="M -14 42 H -8" fill="none" stroke-width="2" stroke="#c4c4c4"></path>
          <circle r="3" cx="-14" cy="42" fill="#c4c4c4"></circle>
        </svg>
      </td>
      <td>
        Gray cell's variables are indirectly used by the second cell. Whiskers
        indicate transitive dependencies
      </td>
    </tr>
    <tr>
      <td>
        <svg viewBox="-18 -8 36 32" width="36" style="color: #ff6565">
          <circle r="3" fill="currentColor"></circle>
          <path d="M 0 0 H 7 V 21 H -7 V 0 Z" fill="none" stroke-width="2" stroke="currentColor"></path>
          <circle r="3" cy="21" fill="currentColor"></circle>
        </svg>
      </td>
      <td>
        Cells have circular dependencies - each uses variables from the other
        (error)
      </td>
    </tr>
  </tbody>
</table>


### Implementation notes

The minimap was heavily inspired by [Observable's
minimap](https://observablehq.com/documentation/debugging/minimap), a
[thoughtfully
designed](https://observablehq.com/@observablehq/introducing-visual-dataflow)
dataflow visualization for their reactive JavaScript notebooks.

We adapted Observable's visual design to marimo's execution model. A key
difference: Observable cells are named (declaring one variable), while marimo
cells can define multiple variables. This leads to asymmetric dataflow tracing.
When tracing upstream, we can identify exactly which variables from a cell
depends on. When tracing downstream, all variables in a dependent cell are
considered affected. Our minimap also accounts for marimo's support for
multi-column layouts.


## Reactive reference highlighting

marimo's **reactive reference highlighting** provides an _in-editor_ indicator
when variables defined by other cells are used in the current cell. These
"reactive references" are emphasized with an underline and lightly bolded text:

<div align="center" style="margin-top: 20px">
<picture>
  <source srcset="/_static/docs-reactive-reference-highlighting.webp" type="image/webp">
  <img src="/_static/docs-reactive-reference-highlighting.jpg" alt="Reactive reference highlighting showing variable usage across cells" style="max-width: 500px; width: 100%;" />
</picture>
</div>

Hover over any underlined variable and `Cmd/Ctrl-Click` to jump to its
definition.

This feature is currently **opt-in** and must be enabled via *Settings* > *User
Settings* > *Display* > *Reference highlighting* or toggled via the command
palette (`Cmd/Ctrl-K` > *Reference highlighting*).

