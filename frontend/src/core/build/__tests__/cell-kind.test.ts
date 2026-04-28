/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { BuildPreviewCell, BuildState } from "../atoms";
import { cellBuildKind } from "../cell-kind";

const c = (id: string) => id as CellId;
const EMPTY_BUILD: BuildState = {
  status: "idle",
  totalCompilable: 0,
  executedCount: 0,
  cellResults: new Map(),
};

const previewOf = (
  cell: BuildPreviewCell,
): Map<CellId, BuildPreviewCell> => new Map([[cell.cellId, cell]]);

describe("cellBuildKind", () => {
  it("ground-truth `compiled`/`cached` collapse to loader; preview is ignored", () => {
    const build: BuildState = {
      ...EMPTY_BUILD,
      cellResults: new Map([
        [
          c("a"),
          {
            cellId: c("a"),
            name: "_",
            displayName: "df",
            state: "executed",
            final: "cached",
          },
        ],
      ]),
    };
    const preview = previewOf({
      cellId: c("a"),
      name: "_",
      displayName: "df",
      predictedKind: "elided",
      confidence: "predicted",
    });
    expect(cellBuildKind(c("a"), build, preview)).toBe("loader");
  });

  it("falls back to the preview's predicted kind", () => {
    const preview = previewOf({
      cellId: c("a"),
      name: "_",
      displayName: "x",
      predictedKind: "elided",
      confidence: "predicted",
    });
    expect(cellBuildKind(c("a"), EMPTY_BUILD, preview)).toBe("elided");
  });

  it("returns `compilable` when only static analysis is available", () => {
    const preview = previewOf({
      cellId: c("a"),
      name: "_",
      displayName: "x",
      predictedKind: null,
      confidence: "static",
    });
    expect(cellBuildKind(c("a"), EMPTY_BUILD, preview)).toBe("compilable");
  });

  it("returns undefined when nothing is known", () => {
    expect(cellBuildKind(c("missing"), EMPTY_BUILD, new Map())).toBeUndefined();
  });
});
