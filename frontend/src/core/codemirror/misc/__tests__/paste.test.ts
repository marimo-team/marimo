/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import {
  type CodemirrorCellActions,
  cellActionsState,
} from "../../cells/state";
import { extractCells, extractMarimoApp, pasteBundle } from "../paste";

describe("extractCells", () => {
  it("returns empty array for non-marimo text", () => {
    expect(extractCells("regular python code")).toEqual([]);
    expect(extractCells("")).toEqual([]);
  });

  it("extracts single cell content", () => {
    const input = `
import marimo as mo
app = mo.App()

@app.cell
def _():
    x = 1
    y = 2
    return (x, y)
`;
    expect(extractCells(input)).toEqual(["x = 1\ny = 2"]);
  });

  it("extracts multiple cells", () => {
    const input = `
import marimo as mo
app = mo.App()

@app.cell
def _():
    import numpy as np
    return np

@app.cell
def _(np):
    data = np.array([1, 2, 3])
    result = data * 2
    return result

if __name__ == "__main__":
    app.run()
`;
    expect(extractCells(input)).toEqual([
      "import numpy as np",
      "data = np.array([1, 2, 3])\nresult = data * 2",
    ]);
  });

  it("handles empty cells", () => {
    const input = `
@app.cell
def _():
    return

@app.cell
def _():
    x = 1
    return x

@app.cell
def _():
    return
`;
    expect(extractCells(input)).toEqual(["x = 1"]);
  });

  it("preserves indentation", () => {
    const input = `
@app.cell
def _():
    if True:
        nested = 1
        if nested:
            deep = 2
    return
`;
    expect(extractCells(input)).toEqual([
      "if True:\n    nested = 1\n    if nested:\n        deep = 2",
    ]);
  });

  it("handles cells with args", () => {
    const input = `
@app.cell
def named_one():
    slider = mo.ui.slider(1, 10)
    button = mo.ui.button("Click")
    return slider, button

@app.cell
def named_two(slider, button):
    mo.hstack([
        slider,
        button
    ])
    return
`;
    expect(extractCells(input)).toEqual([
      'slider = mo.ui.slider(1, 10)\nbutton = mo.ui.button("Click")',
      "mo.hstack([\n    slider,\n    button\n])",
    ]);
  });

  it("handles cells with multi-line args", () => {
    const input = `
@app.cell
def _(
    a,
    b,
    c,
):
    x = a + b + c
    return x
`;
    expect(extractCells(input)).toEqual(["x = a + b + c"]);
  });

  it("handles cells with multi-line args and return", () => {
    const input = `
@app.cell
def _(
    a,
    b,
    c,
):
    x = a + b + c
    return (
        x,
        y,
    )
`;
    expect(extractCells(input)).toEqual(["x = a + b + c"]);
  });

  it("preserves return statements inside nested functions", () => {
    const input = `
@app.cell
def _(mo, px):
    def make_fig():
        data = {'category': ['foo', 'bar'], 'value': [10, 20]}
        fig = px.bar(data, x='category', y='value')
        return fig

    fig = make_fig()
    mo.ui.plotly(fig)
    return
`;
    expect(extractCells(input)).toEqual([
      "def make_fig():\n    data = {'category': ['foo', 'bar'], 'value': [10, 20]}\n    fig = px.bar(data, x='category', y='value')\n    return fig\n\nfig = make_fig()\nmo.ui.plotly(fig)",
    ]);
  });

  it("preserves decorators on nested functions", () => {
    const input = `
@app.cell
def _():
    @functools.cache
    def fib(n):
        return n
    return fib
`;
    expect(extractCells(input)).toEqual([
      "@functools.cache\ndef fib(n):\n    return n",
    ]);
  });

  it("preserves decorated methods inside a class", () => {
    const input = `
@app.cell
def _():
    class A:
        @property
        def x(self):
            return self._x
    return A
`;
    expect(extractCells(input)).toEqual([
      "class A:\n    @property\n    def x(self):\n        return self._x",
    ]);
  });

  it("handles async cells with multi-line args", () => {
    const input = `
@app.cell
async def _(
    a,
    b,
):
    x = await foo(a, b)
    return x
`;
    expect(extractCells(input)).toEqual(["x = await foo(a, b)"]);
  });

  it("strips multi-line returns using brackets", () => {
    const input = `
@app.cell
def _():
    a = 1
    b = 2
    return [
        a,
        b,
    ]
`;
    expect(extractCells(input)).toEqual(["a = 1\nb = 2"]);
  });

  it("strips multi-line returns using braces", () => {
    const input = `
@app.cell
def _():
    a = 1
    return {
        "a": a,
    }
`;
    expect(extractCells(input)).toEqual(["a = 1"]);
  });

  it("does not corrupt the following cell after a bracketed return", () => {
    const input = `
@app.cell
def _():
    a = 1
    return [
        a,
    ]

@app.cell
def _():
    b = 2
    return b
`;
    expect(extractCells(input)).toEqual(["a = 1", "b = 2"]);
  });

  it("preserves comments in the cell body", () => {
    const input = `
@app.cell
def _():
    # leading comment
    x = 1
    return x
`;
    expect(extractCells(input)).toEqual(["# leading comment\nx = 1"]);
  });

  it("extracts the setup block separately from cells", () => {
    const input = `
import marimo
app = marimo.App()

with app.setup(hide_code=True):
    import marimo as mo
    import numpy as np
    from numpy.linalg import eigh
`;
    expect(extractMarimoApp(input)).toEqual({
      setup: "import marimo as mo\nimport numpy as np\nfrom numpy.linalg import eigh",
      cells: [],
    });
    // The convenience wrapper excludes the setup block.
    expect(extractCells(input)).toEqual([]);
  });

  it("extracts @app.function definitions, keeping their return", () => {
    const input = `
@app.function
def laplacian_matrix(adjacency_matrix):
    degree_matrix = np.diag(np.sum(adjacency_matrix, axis=1))
    L = degree_matrix - adjacency_matrix
    return L
`;
    expect(extractCells(input)).toEqual([
      "def laplacian_matrix(adjacency_matrix):\n    degree_matrix = np.diag(np.sum(adjacency_matrix, axis=1))\n    L = degree_matrix - adjacency_matrix\n    return L",
    ]);
  });

  it("extracts setup separately while keeping cells and functions in order", () => {
    const input = `
with app.setup:
    import numpy as np

@app.cell
def _():
    a = 1
    return (a,)

@app.function
def double(x):
    return x * 2
`;
    expect(extractMarimoApp(input)).toEqual({
      setup: "import numpy as np",
      cells: ["a = 1", "def double(x):\n    return x * 2"],
    });
  });

  it("handles cells with config", () => {
    const input = `
@app.cell(hide_code=True, column=2)
def foo():
    x = mo.ui.slider(1, 10)
    return x
`;
    expect(extractCells(input)).toEqual(["x = mo.ui.slider(1, 10)"]);
  });
});

// Mock ClipboardEvent and DataTransfer
class MockDataTransfer {
  private data: Record<string, string> = {};
  setData(format: string, data: string) {
    this.data[format] = data;
  }
  getData(format: string) {
    return this.data[format];
  }
}

class MockClipboardEvent extends Event {
  clipboardData: MockDataTransfer;
  constructor(type: string, init?: { clipboardData?: MockDataTransfer }) {
    super(type);
    this.clipboardData = init?.clipboardData || new MockDataTransfer();
  }
}

describe("pasteBundle", () => {
  it("handles pasting marimo app code", () => {
    const createManyBelow = vi.fn();
    const extension = pasteBundle();
    const view = new EditorView({
      state: EditorState.create({
        doc: "",
        extensions: [
          extension,
          cellActionsState.of({
            createManyBelow,
          } as never as CodemirrorCellActions),
        ],
      }),
    });

    // Mount the view to a DOM element
    // const container = document.createElement("div");

    const clipboardData = new MockDataTransfer();
    clipboardData.setData(
      "text/plain",
      `
@app.cell
def _():
    x = 1
    return x
`,
    );
    const event = new MockClipboardEvent("paste", { clipboardData });

    // HACK: manually add the paste event listener
    // @ts-expect-error extension not typed
    view.dom.onpaste = (evt) => extension[0].domEventHandlers.paste(evt, view);
    view.dom.dispatchEvent(event);

    expect(createManyBelow).toHaveBeenCalledWith(["x = 1"]);
  });

  it("ignores non-marimo pastes", () => {
    const createManyBelow = vi.fn();
    const extension = pasteBundle();
    const view = new EditorView({
      state: EditorState.create({
        doc: "",
        extensions: [
          extension,
          cellActionsState.of({
            createManyBelow,
          } as never as CodemirrorCellActions),
        ],
      }),
    });

    const clipboardData = new MockDataTransfer();
    clipboardData.setData("text/plain", "regular code");
    const event = new MockClipboardEvent("paste", { clipboardData });

    // HACK: manually add the paste event listener
    // @ts-expect-error extension not typed
    view.dom.onpaste = (evt) => extension[0].domEventHandlers.paste(evt, view);

    view.dom.dispatchEvent(event);

    expect(createManyBelow).not.toHaveBeenCalled();
  });

  it("routes the setup block to the setup cell, not a normal cell", () => {
    const createManyBelow = vi.fn();
    const addOrAppendSetupCell = vi.fn();
    const extension = pasteBundle();
    const view = new EditorView({
      state: EditorState.create({
        doc: "",
        extensions: [
          extension,
          cellActionsState.of({
            createManyBelow,
            addOrAppendSetupCell,
          } as never as CodemirrorCellActions),
        ],
      }),
    });

    const clipboardData = new MockDataTransfer();
    clipboardData.setData(
      "text/plain",
      `
with app.setup:
    import numpy as np

@app.cell
def _():
    x = 1
    return x
`,
    );
    const event = new MockClipboardEvent("paste", { clipboardData });

    // HACK: manually add the paste event listener
    // @ts-expect-error extension not typed
    view.dom.onpaste = (evt) => extension[0].domEventHandlers.paste(evt, view);
    view.dom.dispatchEvent(event);

    expect(addOrAppendSetupCell).toHaveBeenCalledWith("import numpy as np");
    expect(createManyBelow).toHaveBeenCalledWith(["x = 1"]);
  });
});
