/* Copyright 2026 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import { computeSlideCellsInfo } from "../compute-slide-cells";
import type { SlideConfig, SlidesLayout } from "../types";
import type { CellId } from "@/core/cells/ids";

interface TestCell {
  id: CellId;
  output: { data: unknown } | null;
}

const DEFAULT_OUTPUT: TestCell["output"] = { data: "ok" };

const cell = (
  id: string,
  output: TestCell["output"] = DEFAULT_OUTPUT,
): TestCell => ({ id: id as CellId, output });

const layoutOf = (entries: Array<[string, SlideConfig]>): SlidesLayout => ({
  cells: new Map(entries.map(([id, cfg]) => [id as CellId, cfg])),
  deck: {},
});

describe("computeSlideCellsInfo", () => {
  it("returns empty results for empty input", () => {
    const result = computeSlideCellsInfo([], layoutOf([]));
    expect(result.cellsWithOutput).toEqual([]);
    expect(result.skippedIds.size).toBe(0);
    expect(result.slideTypes.size).toBe(0);
    expect(result.startCellIndex).toBe(0);
  });

  it("computes firstNonSkippedIndex as the first non-skipped cell", () => {
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b"), cell("c")],
      layoutOf([
        ["a", { type: "skip" }],
        ["b", { type: "skip" }],
        ["c", { type: "slide" }],
      ]),
    );
    expect(result.startCellIndex).toBe(2);
  });

  it("falls back to 0 when every cell is skipped", () => {
    // If the user marked everything as skip we still have to land somewhere;
    // the renderer treats 0 as a safe default rather than rendering nothing.
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b")],
      layoutOf([
        ["a", { type: "skip" }],
        ["b", { type: "skip" }],
      ]),
    );
    expect(result.startCellIndex).toBe(0);
  });

  it("uses index 0 when no cells are skipped", () => {
    const result = computeSlideCellsInfo([cell("a"), cell("b")], layoutOf([]));
    expect(result.startCellIndex).toBe(0);
  });

  it("filters out cells with no output", () => {
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b", null), cell("c")],
      layoutOf([]),
    );
    expect(result.cellsWithOutput.map((c) => c.id)).toEqual(["a", "c"]);
  });

  it("filters out cells whose output data is empty string", () => {
    // Mirrors the editor contract: an explicit empty-string payload means the
    // cell rendered nothing, so it should not occupy a slide.
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b", { data: "" }), cell("c")],
      layoutOf([]),
    );
    expect(result.cellsWithOutput.map((c) => c.id)).toEqual(["a", "c"]);
  });

  it("keeps cells whose output data is a non-empty value (including falsy ones)", () => {
    // Only "" is treated as empty — 0 / false / null-shaped payloads still
    // represent rendered output and should stay in the deck.
    const result = computeSlideCellsInfo(
      [
        cell("a", { data: 0 }),
        cell("b", { data: false }),
        cell("c", { data: null }),
      ],
      layoutOf([]),
    );
    expect(result.cellsWithOutput.map((c) => c.id)).toEqual(["a", "b", "c"]);
  });

  it("populates slideTypes only for cells with an explicit type", () => {
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b"), cell("c")],
      layoutOf([
        ["a", { type: "slide" }],
        ["b", {}],
        ["c", { type: "fragment" }],
      ]),
    );
    expect(Object.fromEntries(result.slideTypes)).toEqual({
      a: "slide",
      c: "fragment",
    });
  });

  it("tracks skipped cells in skippedIds", () => {
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b"), cell("c")],
      layoutOf([
        ["a", { type: "slide" }],
        ["b", { type: "skip" }],
        ["c", { type: "skip" }],
      ]),
    );
    expect([...result.skippedIds]).toEqual(["b", "c"]);
    // Skipped cells are still "visible" deck cells — they just aren't rendered
    // in reveal. The minimap relies on the full list plus skippedIds.
    expect(result.cellsWithOutput.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect(result.slideTypes.get("b" as CellId)).toBe("skip");
  });

  it("ignores layout entries for cells that have no output", () => {
    // If a cell was skipped in the layout but no longer produces output (e.g.
    // the user deleted its code), it should drop out of both maps — otherwise
    // the skip set would reference ghosts.
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b", null)],
      layoutOf([
        ["a", { type: "slide" }],
        ["b", { type: "skip" }],
      ]),
    );
    expect(result.cellsWithOutput.map((c) => c.id)).toEqual(["a"]);
    expect(result.skippedIds.size).toBe(0);
    expect(result.slideTypes.has("b" as CellId)).toBe(false);
  });

  it("preserves the input order of cells in cellsWithOutput", () => {
    const result = computeSlideCellsInfo(
      [cell("c"), cell("a"), cell("b")],
      layoutOf([]),
    );
    expect(result.cellsWithOutput.map((c) => c.id)).toEqual(["c", "a", "b"]);
  });
});
