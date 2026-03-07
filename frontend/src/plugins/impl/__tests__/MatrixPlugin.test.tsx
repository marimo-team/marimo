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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
    const result = plugin.validator.safeParse({
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
    });
    expect(result.success).toBe(true);
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
