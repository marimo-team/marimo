/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import { deserializeLayout, getCellRendererPlugin } from "../plugins";

function makeCell(id: string): CellData {
  return {
    id: id as CellId,
    name: id,
    code: "",
    edited: false,
    lastCodeRun: null,
    lastExecutionTime: null,
    config: { hide_code: false, disabled: false, column: null },
    serializedEditorState: null,
  };
}

describe("getCellRendererPlugin", () => {
  it("returns the matching plugin keyed by layout type", () => {
    expect(getCellRendererPlugin("vertical").type).toBe("vertical");
    expect(getCellRendererPlugin("grid").type).toBe("grid");
    expect(getCellRendererPlugin("slides").type).toBe("slides");
  });
});

describe("deserializeLayout", () => {
  it("deserializes valid grid layout data", () => {
    const layout = deserializeLayout({
      type: "grid",
      data: {
        columns: 12,
        rowHeight: 20,
        cells: [{ position: [1, 2, 3, 4] }],
      },
      cells: [makeCell("a")],
    });

    expect(layout.columns).toBe(12);
    expect(layout.cells).toEqual([{ i: "a", x: 1, y: 2, w: 3, h: 4 }]);
  });

  it("deserializes valid slides layout data", () => {
    const layout = deserializeLayout({
      type: "slides",
      data: {
        cells: [{ type: "fragment" }],
        deck: { transition: "fade" },
      },
      cells: [makeCell("a")],
    });

    expect(layout.deck).toEqual({ transition: "fade" });
    expect(layout.cells.get("a" as CellId)).toEqual({ type: "fragment" });
  });

  it("vertical layout is always null regardless of stored data", () => {
    // Older save files may have arbitrary `data` for vertical; we must
    // ignore it because `VerticalLayout = null`.
    const layout = deserializeLayout({
      type: "vertical",
      data: { something: "unexpected" },
      cells: [makeCell("a")],
    });

    expect(layout).toBeNull();
  });

  it("tolerates legacy `null` for optional grid fields", () => {
    // Older marimo versions wrote unset optional fields as `null`
    // (e.g. `"maxWidth": null` in `layout_grid_with_sidebar.grid.json`).
    // Those files must keep loading.
    const layout = deserializeLayout({
      type: "grid",
      data: {
        columns: 24,
        rowHeight: 20,
        maxWidth: null,
        bordered: true,
        cells: [{ position: [0, 0, 5, 2] }, { position: null }],
      },
      cells: [makeCell("a"), makeCell("b")],
    });

    expect(layout.columns).toBe(24);
    expect(layout.cells).toEqual([{ i: "a", x: 0, y: 0, w: 5, h: 2 }]);
  });
});
