/* Copyright 2026 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { IPluginProps } from "../../types";
import { MatrixPlugin } from "../MatrixPlugin";

function makeProps(
  overrides: Partial<IPluginProps<number[][], ReturnType<MatrixPlugin["validator"]["parse"]>>> = {},
): IPluginProps<number[][], ReturnType<MatrixPlugin["validator"]["parse"]>> {
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

  it("renders disabled cells with disabled class", () => {
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

    expect(getByTestId("matrix-cell-0-0").className).toContain("disabled");
    expect(getByTestId("matrix-cell-0-1").className).not.toContain("disabled");
    expect(getByTestId("matrix-cell-1-0").className).not.toContain("disabled");
    expect(getByTestId("matrix-cell-1-1").className).toContain("disabled");
  });

  it("renders row labels", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        rowLabels: ["Row A", "Row B"],
      },
    });
    const { container } = render(plugin.render(props));

    const labels = container.querySelectorAll(".marimo-matrix-row-label");
    expect(labels).toHaveLength(2);
    expect(labels[0].textContent).toBe("Row A");
    expect(labels[1].textContent).toBe("Row B");
  });

  it("renders column labels", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      data: {
        ...makeProps().data,
        columnLabels: ["Col X", "Col Y"],
      },
    });
    const { container } = render(plugin.render(props));

    const labels = container.querySelectorAll(".marimo-matrix-column-label");
    expect(labels).toHaveLength(2);
    expect(labels[0].textContent).toBe("Col X");
    expect(labels[1].textContent).toBe("Col Y");
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
      initialValue: [[1, 2], [3, 4]],
      label: "test",
      minValue: null,
      maxValue: null,
      step: [[1, 1], [1, 1]],
      precision: 1,
      rowLabels: null,
      columnLabels: null,
      symmetric: false,
      scientific: false,
      disabled: [[false, false], [false, false]],
    });
    expect(result.success).toBe(true);
  });

  it("displays values in scientific notation", () => {
    const plugin = new MatrixPlugin();
    const props = makeProps({
      value: [
        [0.00153, 1234567],
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
});
