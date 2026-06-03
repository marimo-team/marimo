/* Copyright 2026 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import { computeSlideCellsInfo } from "../compute-slide-cells";
import type { SlideConfig, SlidesLayout } from "../types";
import type { CellId } from "@/core/cells/ids";
import { cellId } from "@/__tests__/branded";

interface TestCell {
  id: CellId;
  output: { data: unknown } | null;
}

const DEFAULT_OUTPUT: TestCell["output"] = { data: "ok" };

const cell = (
  id: string,
  output: TestCell["output"] = DEFAULT_OUTPUT,
): TestCell => ({ id: cellId(id), output });

const layoutOf = (entries: Array<[string, SlideConfig]>): SlidesLayout => ({
  cells: new Map(entries.map(([id, cfg]) => [cellId(id), cfg])),
  deck: {},
});

describe("computeSlideCellsInfo", () => {
  it("returns empty results for empty input", () => {
    const result = computeSlideCellsInfo([], layoutOf([]));
    expect(result.slideCells).toEqual([]);
    expect(result.skippedIds.size).toBe(0);
    expect(result.noOutputIds.size).toBe(0);
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

  it("keeps cells with no output for the minimap", () => {
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b", null), cell("c")],
      layoutOf([]),
    );
    expect(result.slideCells.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect([...result.noOutputIds]).toEqual(["b"]);
    expect([...result.skippedIds]).toEqual(["b"]);
  });

  it("keeps cells whose output data is empty string for the minimap", () => {
    // Mirrors the editor contract: an explicit empty-string payload means the
    // cell rendered nothing, so it should not occupy a reveal slide.
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b", { data: "" }), cell("c")],
      layoutOf([]),
    );
    expect(result.slideCells.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect([...result.noOutputIds]).toEqual(["b"]);
    expect([...result.skippedIds]).toEqual(["b"]);
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
    expect(result.slideCells.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect(result.noOutputIds.size).toBe(0);
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
    expect(result.slideCells.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect(result.slideTypes.get(cellId("b"))).toBe("skip");
  });

  it("preserves configured slide types for cells that have no output", () => {
    // The missing output is transient runtime state, not persisted slide config.
    const result = computeSlideCellsInfo(
      [cell("a"), cell("b", null)],
      layoutOf([
        ["a", { type: "slide" }],
        ["b", { type: "skip" }],
      ]),
    );
    expect(result.slideCells.map((c) => c.id)).toEqual(["a", "b"]);
    expect([...result.noOutputIds]).toEqual(["b"]);
    expect([...result.skippedIds]).toEqual(["b"]);
    expect(result.slideTypes.get(cellId("b"))).toBe("skip");
  });

  it("skips no-output cells when computing the starting cell", () => {
    const result = computeSlideCellsInfo(
      [cell("a", null), cell("b", { data: "" }), cell("c")],
      layoutOf([]),
    );
    expect(result.startCellIndex).toBe(2);
  });

  it("preserves the input order of cells in slideCells", () => {
    const result = computeSlideCellsInfo(
      [cell("c"), cell("a"), cell("b")],
      layoutOf([]),
    );
    expect(result.slideCells.map((c) => c.id)).toEqual(["c", "a", "b"]);
  });
});
