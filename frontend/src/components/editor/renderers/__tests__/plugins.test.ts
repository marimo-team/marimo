/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import { Logger } from "@/utils/Logger";
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

  it("falls back to the plugin's initial layout when validation fails", () => {
    // Regression: corrupted layout JSON used to crash inside the plugin's
    // deserializer. It must now fall back to a default and warn.
    const warnSpy = vi.spyOn(Logger, "warn").mockImplementation(() => {});

    const layout = deserializeLayout({
      type: "slides",
      data: { cells: [{ type: "not-a-real-slide-type" }] },
      cells: [makeCell("a")],
    });

    // Initial slides layout has no per-cell entries.
    expect(layout.cells.size).toBe(0);
    expect(layout.deck).toEqual({});
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Invalid serialized layout for "slides"'),
      expect.anything(),
    );
    warnSpy.mockRestore();
  });

  it("falls back to default when grid data is the wrong shape", () => {
    const warnSpy = vi.spyOn(Logger, "warn").mockImplementation(() => {});

    const layout = deserializeLayout({
      type: "grid",
      data: "definitely not a grid layout",
      cells: [makeCell("a")],
    });

    // Should return the grid plugin's initial layout (defined in
    // grid-layout/plugin.tsx, currently 24 columns) rather than throwing.
    expect(layout).toEqual(
      getCellRendererPlugin("grid").getInitialLayout([makeCell("a")]),
    );
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});
