/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi } from "vitest";
import { extractCells, pasteBundle } from "../paste";
import { EditorView } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import {
  cellActionsState,
  type CodemirrorCellActions,
} from "../../cells/state";

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
});
