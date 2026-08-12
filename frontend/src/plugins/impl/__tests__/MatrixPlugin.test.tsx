/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { IPluginProps } from "../../types";
import { MatrixPlugin } from "../MatrixPlugin";

type PluginData = ReturnType<MatrixPlugin["validator"]["parse"]>;

function makeProps(
  overrides: Partial<IPluginProps<number[][], PluginData>> = {},
): IPluginProps<number[][], PluginData> {
  return {
    host: document.createElement("div"),
    value: [
      [1, 2],
      [3, 4],
    ],
    setValue: vi.fn(),
    data: {
      initialValue: [
        [1, 2],
        [3, 4],
      ],
      label: null,
      minValue: null,
      maxValue: null,
      step: [
        [1, 1],
        [1, 1],
      ],
      precision: 1,
      rowLabels: null,
      columnLabels: null,
      symmetric: false,
      debounce: false,
      scientific: false,
      disabled: [
        [false, false],
        [false, false],
      ],
    },
    functions: {},
    ...overrides,
  };
}

beforeEach(() => {
  // jsdom doesn't implement pointer capture
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();

  // jsdom's PointerEvent doesn't properly inherit MouseEvent properties
  // like clientX. Polyfill it so fireEvent.pointerDown/Move/Up work.
  // oxlint-disable-next-line typescript/no-explicit-any
  (globalThis as any).PointerEvent = class PointerEvent extends MouseEvent {
    readonly pointerId: number;
    constructor(type: string, init: PointerEventInit = {}) {
      super(type, init);
      this.pointerId = init.pointerId ?? 0;
    }
  };
});

describe("MatrixPlugin", () => {
  it("renders correct number of cells", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps();
    const { getAllByTestId } = render(plugin.render(props));

    const cells = getAllByTestId(/^matrix-cell-/);
    expect(cells).toHaveLength(4);
  });

  it("displays values with correct precision", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      value: [
        [1.5, 2.123],
        [3, 4.9],
      ],
      data: {
        ...makeProps().data,
        precision: 2,
      },
    });
    const { getByTestId } = render(plugin.render(props));

    expect(getByTestId("matrix-cell-0-0").textContent).toBe("1.50");
    expect(getByTestId("matrix-cell-0-1").textContent).toBe("2.12");
    expect(getByTestId("matrix-cell-1-0").textContent).toBe("3.00");
    expect(getByTestId("matrix-cell-1-1").textContent).toBe("4.90");
  });

  it("renders disabled cells with aria-disabled", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        disabled: [
          [true, false],
          [false, true],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));

    expect(getByTestId("matrix-cell-0-0").getAttribute("aria-disabled")).toBe(
      "true",
    );
    expect(getByTestId("matrix-cell-0-1").hasAttribute("aria-disabled")).toBe(
      false,
    );
    expect(getByTestId("matrix-cell-1-0").hasAttribute("aria-disabled")).toBe(
      false,
    );
    expect(getByTestId("matrix-cell-1-1").getAttribute("aria-disabled")).toBe(
      "true",
    );
  });

  it("renders row labels", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        rowLabels: ["Row A", "Row B"],
      },
    });
    const { getByText } = render(plugin.render(props));

    expect(getByText("Row A")).toBeDefined();
    expect(getByText("Row B")).toBeDefined();
  });

  it("renders column labels", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        columnLabels: ["Col X", "Col Y"],
      },
    });
    const { getByText } = render(plugin.render(props));

    expect(getByText("Col X")).toBeDefined();
    expect(getByText("Col Y")).toBeDefined();
  });

  it("renders a 3x3 matrix", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      value: [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      data: {
        ...makeProps().data,
        step: [
          [1, 1, 1],
          [1, 1, 1],
          [1, 1, 1],
        ],
        disabled: [
          [false, false, false],
          [false, false, false],
          [false, false, false],
        ],
      },
    });
    const { getAllByTestId } = render(plugin.render(props));

    const cells = getAllByTestId(/^matrix-cell-/);
    expect(cells).toHaveLength(9);
  });

  it("validates with zod schema", () => {
    const plugin = new MatrixPlugin();
    const payload = {
      initialValue: [
        [1, 2],
        [3, 4],
      ],
      label: "test",
      minValue: null,
      maxValue: null,
      step: [
        [1, 1],
        [1, 1],
      ],
      precision: 1,
      rowLabels: null,
      columnLabels: null,
      symmetric: false,
      scientific: false,
      disabled: [
        [false, false],
        [false, false],
      ],
    };
    // debounce is optional and defaults off
    expect(plugin.validator.parse(payload).debounce).toBe(false);
    expect(plugin.validator.safeParse({ ...payload, step: null }).success).toBe(
      false,
    );
  });

  it("displays values in scientific notation", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      value: [
        [0.001_53, 1_234_567],
        [0, -0.042],
      ],
      data: {
        ...makeProps().data,
        scientific: true,
        precision: 2,
      },
    });
    const { getByTestId } = render(plugin.render(props));

    expect(getByTestId("matrix-cell-0-0").textContent).toBe("1.53e-3");
    expect(getByTestId("matrix-cell-0-1").textContent).toBe("1.23e+6");
    expect(getByTestId("matrix-cell-1-0").textContent).toBe("0.00e+0");
    expect(getByTestId("matrix-cell-1-1").textContent).toBe("-4.20e-2");
  });

  it("drag adjusts cell value", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    // Pointer down on cell (0,0), then move 30px right = 3 steps
    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 130 });
    fireEvent.pointerUp(container);

    expect(setValueMock).toHaveBeenCalledWith([
      [3, 0],
      [0, 0],
    ]);
  });

  it("symmetric mode mirrors value to transpose cell", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        symmetric: true,
      },
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-1");
    const container = getByTestId("marimo-plugin-matrix");

    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 120 }); // 2 steps
    fireEvent.pointerUp(container);

    // Cell (0,1) and (1,0) should both be 2
    expect(setValueMock).toHaveBeenCalledWith([
      [0, 2],
      [2, 0],
    ]);
  });

  it("ArrowUp increments cell value", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "ArrowUp" });

    expect(setValueMock).toHaveBeenCalledWith([
      [6, 0],
      [0, 0],
    ]);
  });

  it("ArrowUp preserves significant digits in large cell values", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [1_234_567_890_123, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "ArrowUp" });

    expect(setValueMock).toHaveBeenCalledWith([
      [1_234_567_890_124, 0],
      [0, 0],
    ]);
  });

  it("ArrowDown decrements cell value", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "ArrowDown" });

    expect(setValueMock).toHaveBeenCalledWith([
      [4, 0],
      [0, 0],
    ]);
  });

  it("disabled cells ignore pointer and keyboard input", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        disabled: [
          [true, false],
          [false, false],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    // Keyboard
    fireEvent.keyDown(cell, { key: "ArrowUp" });
    expect(setValueMock).not.toHaveBeenCalled();

    // Drag
    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 130 });
    fireEvent.pointerUp(container);
    expect(setValueMock).not.toHaveBeenCalled();
  });

  it("clamps values to min/max bounds", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        minValue: [
          [0, 0],
          [0, 0],
        ],
        maxValue: [
          [6, 10],
          [10, 10],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    // Try to drag far right (would be +10 without clamping)
    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 200 });
    fireEvent.pointerUp(container);

    // Should be clamped to max of 6
    expect(setValueMock).toHaveBeenCalledWith([
      [6, 0],
      [0, 0],
    ]);
  });

  it("with debounce, defers setValue until the drag ends", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        debounce: true,
      },
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 130 });

    // The dragged value renders locally but is not emitted yet.
    expect(cell.textContent).toBe("3.0");
    expect(setValueMock).not.toHaveBeenCalled();

    fireEvent.pointerUp(container);
    expect(setValueMock).toHaveBeenCalledExactlyOnceWith([
      [3, 0],
      [0, 0],
    ]);
  });

  it("sets aria attributes on cells", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        rowLabels: ["x", "y"],
        columnLabels: ["a", "b"],
        minValue: [
          [0, 0],
          [0, 0],
        ],
        maxValue: [
          [10, 10],
          [10, 10],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-1");

    expect(cell.getAttribute("aria-label")).toBe("x, b");
    expect(cell.getAttribute("aria-valuenow")).toBe("2");
    expect(cell.getAttribute("aria-valuemin")).toBe("0");
    expect(cell.getAttribute("aria-valuemax")).toBe("10");
    expect(cell.getAttribute("tabindex")).toBe("0");
  });
});

describe("MatrixPlugin cell editing", () => {
  it("double-click opens an editor prefilled with the exact value", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps();
    const { getByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));

    const input = getByTestId("matrix-input-0-0") as HTMLInputElement;
    expect(input.value).toBe("1");
  });

  it("commits a typed scientific-notation value on Enter", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({ setValue: setValueMock });
    const { getByTestId, queryByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    const input = getByTestId("matrix-input-0-0");
    fireEvent.change(input, { target: { value: "2.32e7" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // Exactly once: the blur fired while refocusing the cell must not
    // commit a second time.
    expect(setValueMock).toHaveBeenCalledExactlyOnceWith([
      [23_200_000, 2],
      [3, 4],
    ]);
    expect(queryByTestId("matrix-input-0-0")).toBeNull();
  });

  it("does not snap typed values to step", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({ setValue: setValueMock });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    const input = getByTestId("matrix-input-0-0");
    fireEvent.change(input, { target: { value: "2.5" } });
    fireEvent.keyDown(input, { key: "Enter" });

    // step is 1, but the typed value is exact
    expect(setValueMock).toHaveBeenCalledWith([
      [2.5, 2],
      [3, 4],
    ]);
  });

  it("commits on blur", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({ setValue: setValueMock });
    const { getByTestId, queryByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    const input = getByTestId("matrix-input-0-0");
    fireEvent.change(input, { target: { value: "42" } });
    fireEvent.blur(input);

    expect(setValueMock).toHaveBeenCalledWith([
      [42, 2],
      [3, 4],
    ]);
    expect(queryByTestId("matrix-input-0-0")).toBeNull();
  });

  it("Escape cancels without committing", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({ setValue: setValueMock });
    const { getByTestId, queryByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    const input = getByTestId("matrix-input-0-0");
    fireEvent.change(input, { target: { value: "42" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(setValueMock).not.toHaveBeenCalled();
    expect(queryByTestId("matrix-input-0-0")).toBeNull();
  });

  it("discards invalid input and closes the editor", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({ setValue: setValueMock });
    const { getByTestId, queryByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    const input = getByTestId("matrix-input-0-0");
    fireEvent.change(input, { target: { value: "abc" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(setValueMock).not.toHaveBeenCalled();
    expect(queryByTestId("matrix-input-0-0")).toBeNull();
  });

  it("clamps typed values to bounds", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        maxValue: [
          [10, 10],
          [10, 10],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    const input = getByTestId("matrix-input-0-0");
    fireEvent.change(input, { target: { value: "50" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(setValueMock).toHaveBeenCalledWith([
      [10, 2],
      [3, 4],
    ]);
  });

  it("mirrors typed values in symmetric mode", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        symmetric: true,
      },
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-1"));
    const input = getByTestId("matrix-input-0-1");
    fireEvent.change(input, { target: { value: "7" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(setValueMock).toHaveBeenCalledWith([
      [0, 7],
      [7, 0],
    ]);
  });

  it("keeps the symmetric mirror within the transpose cell's bounds", () => {
    // Asymmetric per-cell bounds on a symmetric matrix: [0][1] allows up to
    // 100, but its transpose [1][0] is capped at 5. Editing [0][1] must not
    // smuggle an out-of-bounds value into the mirror, and the pair must stay
    // equal — so the shared value is clamped to the intersection (max 5).
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        symmetric: true,
        maxValue: [
          [100, 100],
          [5, 100],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-1"));
    const input = getByTestId("matrix-input-0-1");
    fireEvent.change(input, { target: { value: "7" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(setValueMock).toHaveBeenCalledWith([
      [0, 5],
      [5, 0],
    ]);
  });

  it("emits nothing when clamping leaves the value unchanged", () => {
    // Already at the transpose's cap of 5: dragging or typing past it must
    // not fire setValue with an identical matrix.
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 5],
        [5, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        symmetric: true,
        maxValue: [
          [100, 100],
          [5, 100],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-1");
    const container = getByTestId("marimo-plugin-matrix");

    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 130 });
    fireEvent.pointerUp(container);

    fireEvent.doubleClick(cell);
    const input = getByTestId("matrix-input-0-1");
    fireEvent.change(input, { target: { value: "7" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(setValueMock).not.toHaveBeenCalled();
  });

  it("Enter opens the editor from the keyboard", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps();
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "Enter" });

    const input = getByTestId("matrix-input-0-0") as HTMLInputElement;
    expect(input.value).toBe("1");
  });

  it("typing a digit starts editing seeded with that digit", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps();
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "5" });

    const input = getByTestId("matrix-input-0-0") as HTMLInputElement;
    expect(input.value).toBe("5");
  });

  it("does not open an editor on disabled cells", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        disabled: [
          [true, false],
          [false, false],
        ],
      },
    });
    const { getByTestId, queryByTestId } = render(plugin.render(props));

    fireEvent.doubleClick(getByTestId("matrix-cell-0-0"));
    expect(queryByTestId("matrix-input-0-0")).toBeNull();

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "Enter" });
    expect(queryByTestId("matrix-input-0-0")).toBeNull();
  });
});

describe("MatrixPlugin modifier scrubbing", () => {
  it("shift+drag scrubs at 10x step", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1, shiftKey: true });
    fireEvent.pointerMove(container, { clientX: 130, shiftKey: true });
    fireEvent.pointerUp(container);

    expect(setValueMock).toHaveBeenCalledWith([
      [30, 0],
      [0, 0],
    ]);
  });

  it("alt+drag scrubs at 0.1x step", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1, altKey: true });
    fireEvent.pointerMove(container, { clientX: 130, altKey: true });
    fireEvent.pointerUp(container);

    expect(setValueMock).toHaveBeenCalledWith([
      [0.3, 0],
      [0, 0],
    ]);
  });

  it("pressing shift mid-drag rescales future movement without jumping", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");
    const container = getByTestId("marimo-plugin-matrix");

    fireEvent.pointerDown(cell, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(container, { clientX: 130 }); // +3
    fireEvent.pointerMove(container, { clientX: 130, shiftKey: true }); // rebase
    fireEvent.pointerMove(container, { clientX: 160, shiftKey: true }); // +30
    fireEvent.pointerUp(container);

    expect(setValueMock).toHaveBeenLastCalledWith([
      [33, 0],
      [0, 0],
    ]);
  });

  it("shift+ArrowUp increments by 10x step", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), {
      key: "ArrowUp",
      shiftKey: true,
    });

    expect(setValueMock).toHaveBeenCalledWith([
      [15, 0],
      [0, 0],
    ]);
  });

  it("alt+ArrowDown decrements by 0.1x step", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), {
      key: "ArrowDown",
      altKey: true,
    });

    expect(setValueMock).toHaveBeenCalledWith([
      [4.9, 0],
      [0, 0],
    ]);
  });

  it("keeps tiny step values instead of rounding them to zero", () => {
    // 2e-14 sits below the absolute noise threshold for values of ordinary
    // magnitude; the tolerance must scale with the step to preserve it.
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [0, 0],
        [0, 0],
      ],
      setValue: setValueMock,
      data: {
        ...makeProps().data,
        step: [
          [2e-14, 1],
          [1, 1],
        ],
      },
    });
    const { getByTestId } = render(plugin.render(props));

    fireEvent.keyDown(getByTestId("matrix-cell-0-0"), { key: "ArrowUp" });

    expect(setValueMock).toHaveBeenCalledWith([
      [2e-14, 0],
      [0, 0],
    ]);
  });

  it("PageUp and PageDown step by 10x", () => {
    const plugin = new MatrixPlugin();
    const setValueMock = vi.fn();
    const props = makeProps({
      value: [
        [5, 0],
        [0, 0],
      ],
      setValue: setValueMock,
    });
    const { getByTestId } = render(plugin.render(props));
    const cell = getByTestId("matrix-cell-0-0");

    fireEvent.keyDown(cell, { key: "PageUp" });
    expect(setValueMock).toHaveBeenCalledWith([
      [15, 0],
      [0, 0],
    ]);

    fireEvent.keyDown(cell, { key: "PageDown" });
    expect(setValueMock).toHaveBeenCalledWith([
      [-5, 0],
      [0, 0],
    ]);
  });
});
