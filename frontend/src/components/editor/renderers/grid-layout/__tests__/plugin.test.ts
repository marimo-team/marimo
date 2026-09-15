/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { deserializeLayout } from "../../plugins";

describe("GridLayoutPlugin validation", () => {
  it("preserves valid cell positions while normalizing optional fields", () => {
    const a = cellId("a");
    const b = cellId("b");
    const { cellData } = MockNotebook.notebookState({
      cellData: { [a]: {}, [b]: {} },
    });
    const layout = deserializeLayout({
      type: "grid",
      data: {
        columns: 12,
        rowHeight: 20,
        maxWidth: null,
        cells: [
          {
            position: [0, 0, 6, 4],
            side: "right",
          },
          {
            position: [1, 4, 6, 4],
            side: "future-side",
          },
        ],
      },
      cells: [cellData[a], cellData[b]],
    });

    expect(layout.maxWidth).toBeUndefined();
    expect(layout.cellSide).toEqual(new Map([["a", "right"]]));
    expect(layout.cells).toEqual([
      { i: "a", x: 0, y: 0, w: 6, h: 4 },
      { i: "b", x: 1, y: 4, w: 6, h: 4 },
    ]);
  });
});
