/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { FieldTypes } from "@/components/data-table/types";
import { applyEditorEdits } from "../editor-state";

describe("applyEditorEdits", () => {
  it("replays edits against an empty table", () => {
    const result = applyEditorEdits(
      { data: [], columnFields: new Map([["value", "unknown"]]) },
      [{ rowIdx: 0, columnId: "value", value: "first" }],
    );

    expect(result.data).toEqual([{ value: "first" }]);
  });

  it("replays an append after deleting every row", () => {
    const result = applyEditorEdits(
      {
        data: [{ A: 1, B: "a" }],
        columnFields: new Map([
          ["A", "number"],
          ["B", "string"],
        ]) as FieldTypes,
      },
      [
        { rowIdx: 0, type: "remove" },
        { rowIdx: 0, columnId: "A", value: 2 },
        { rowIdx: 0, columnId: "B", value: "b" },
      ],
    );

    expect(result.data).toEqual([{ A: 2, B: "b" }]);
  });

  it("uses the evolving column order", () => {
    const result = applyEditorEdits(
      {
        data: [{ A: "a", B: "b" }],
        columnFields: new Map([
          ["A", "string"],
          ["B", "string"],
        ]) as FieldTypes,
      },
      [
        { columnIdx: 0, type: "remove" },
        { columnIdx: 0, type: "rename", newName: "D" },
      ],
    );

    expect(result.data).toEqual([{ D: "b" }]);
    expect([...result.columnFields]).toEqual([["D", "string"]]);
  });

  it("preserves inserted column order through later edits", () => {
    const result = applyEditorEdits(
      {
        data: [{ A: "a", C: "c" }],
        columnFields: new Map([
          ["A", "string"],
          ["C", "string"],
        ]) as FieldTypes,
      },
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

  it("does not mutate the previous state", () => {
    const state = {
      data: [{ A: "before" }],
      columnFields: new Map([["A", "string"]]) as FieldTypes,
    };

    const result = applyEditorEdits(state, [
      { rowIdx: 0, columnId: "A", value: "after" },
      { columnIdx: 1, type: "insert", newName: "B" },
    ]);

    expect(state.data).toEqual([{ A: "before" }]);
    expect([...state.columnFields]).toEqual([["A", "string"]]);
    expect(result.data).toEqual([{ A: "after", B: "" }]);
  });

  it("ignores negative row indices", () => {
    const state = {
      data: [{ A: "unchanged" }],
      columnFields: new Map([["A", "string"]]) as FieldTypes,
    };

    expect(
      applyEditorEdits(state, [
        { rowIdx: -1, columnId: "A", value: "invalid" },
        { rowIdx: -1, type: "remove" },
      ]).data,
    ).toEqual(state.data);
  });
});
