/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { FieldTypes } from "@/components/data-table/types";
import { replayEdits } from "../replay-edits";

describe("replayEdits", () => {
  it("replays edits against an empty table", () => {
    const result = replayEdits([], new Map([["value", "unknown"]]), [
      { rowIdx: 0, columnId: "value", value: "first" },
    ]);

    expect(result.data).toEqual([{ value: "first" }]);
  });

  it("replays an append after deleting every row", () => {
    const result = replayEdits(
      [{ A: 1, B: "a" }],
      new Map([
        ["A", "number"],
        ["B", "string"],
      ]) as FieldTypes,
      [
        { rowIdx: 0, type: "remove" },
        { rowIdx: 0, columnId: "A", value: 2 },
        { rowIdx: 0, columnId: "B", value: "b" },
      ],
    );

    expect(result.data).toEqual([{ A: 2, B: "b" }]);
  });

  it("uses the evolving column order", () => {
    const result = replayEdits(
      [{ A: "a", B: "b" }],
      new Map([
        ["A", "string"],
        ["B", "string"],
      ]) as FieldTypes,
      [
        { columnIdx: 0, type: "remove" },
        { columnIdx: 0, type: "rename", newName: "D" },
      ],
    );

    expect(result.data).toEqual([{ D: "b" }]);
    expect([...result.columnFields]).toEqual([["D", "string"]]);
  });

  it("preserves inserted column order through later edits", () => {
    const result = replayEdits(
      [{ A: "a", C: "c" }],
      new Map([
        ["A", "string"],
        ["C", "string"],
      ]) as FieldTypes,
      [
        {
          columnIdx: 1,
          type: "insert",
          newName: "B",
          dataType: "boolean",
        },
        { columnIdx: 1, type: "rename", newName: "D" },
        { columnIdx: 2, type: "remove" },
      ],
    );

    expect(result.data).toEqual([{ A: "a", D: "" }]);
    expect(Object.keys(result.data[0])).toEqual(["A", "D"]);
    expect([...result.columnFields]).toEqual([
      ["A", "string"],
      ["D", "boolean"],
    ]);
  });
});
