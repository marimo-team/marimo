/* Copyright 2024 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import { MultiColumn } from "@/utils/id-tree";
import type { CellSelectionState } from "../selection";
import { exportedForTesting } from "../selection";

const { initialState, reducer, createActions } = exportedForTesting;

const CellIds = {
  a: "a" as CellId,
  b: "b" as CellId,
  c: "c" as CellId,
  d: "d" as CellId,
  e: "e" as CellId,
};

describe("cell selection reducer", () => {
  let state: CellSelectionState;

  const actions = createActions((action) => {
    state = reducer(state, action);
  });

  beforeEach(() => {
    state = initialState();
  });

  it("should have initial state", () => {
    expect(state).toEqual({
      selectionStart: null,
      selectionEnd: null,
      selected: new Set(),
    });
  });

  it("should select a single cell", () => {
    actions.select({ cellId: CellIds.a });

    expect(state).toEqual({
      selectionStart: CellIds.a,
      selectionEnd: CellIds.a,
      selected: new Set([CellIds.a]),
    });
  });

  it("should replace selection when selecting a different cell", () => {
    actions.select({ cellId: CellIds.a });
    actions.select({ cellId: CellIds.b });

    expect(state).toEqual({
      selectionStart: CellIds.b,
      selectionEnd: CellIds.b,
      selected: new Set([CellIds.b]),
    });
  });

  it("should extend selection forward", () => {
    const allCellIds = MultiColumn.from([
      [CellIds.a, CellIds.b, CellIds.c, CellIds.d],
    ]);

    // First select cell a
    actions.select({ cellId: CellIds.a });

    // Then extend to cell c
    actions.extend({ cellId: CellIds.c, allCellIds });

    expect(state).toEqual({
      selectionStart: CellIds.a,
      selectionEnd: CellIds.c,
      selected: new Set([CellIds.a, CellIds.b, CellIds.c]),
    });
  });

  it("should extend selection backward", () => {
    const allCellIds = MultiColumn.from([
      [CellIds.a, CellIds.b, CellIds.c, CellIds.d],
    ]);

    // First select cell c
    actions.select({ cellId: CellIds.c });

    // Then extend to cell a (backward)
    actions.extend({ cellId: CellIds.a, allCellIds });

    expect(state).toEqual({
      selectionStart: CellIds.c,
      selectionEnd: CellIds.a,
      selected: new Set([CellIds.a, CellIds.b, CellIds.c]),
    });
  });

  it("should extend selection to same cell", () => {
    const allCellIds = MultiColumn.from([[CellIds.a, CellIds.b, CellIds.c]]);

    // First select cell b
    actions.select({ cellId: CellIds.b });

    // Then extend to same cell
    actions.extend({ cellId: CellIds.b, allCellIds });

    expect(state).toEqual({
      selectionStart: CellIds.b,
      selectionEnd: CellIds.b,
      selected: new Set([CellIds.b]),
    });
  });

  it("should fallback to single select when extending without selectionStart", () => {
    const allCellIds = MultiColumn.from([[CellIds.a, CellIds.b, CellIds.c]]);

    // Try to extend without any previous selection
    actions.extend({ cellId: CellIds.b, allCellIds });

    expect(state).toEqual({
      selectionStart: CellIds.b,
      selectionEnd: CellIds.b,
      selected: new Set([CellIds.b]),
    });
  });

  it("should fallback to single select when extending with invalid cell ids", () => {
    const allCellIds = MultiColumn.from([[CellIds.a, CellIds.b, CellIds.c]]);

    // Create a state with invalid selection start (not in allCellIds)
    const invalidState = {
      selectionStart: CellIds.d, // not in allCellIds
      selectionEnd: CellIds.d,
      selected: new Set([CellIds.d]),
    };

    // Test reducer directly since we need to start with custom state
    const result = reducer(invalidState, {
      type: "extend",
      payload: { cellId: CellIds.b, allCellIds },
    });

    expect(result).toEqual({
      selectionStart: CellIds.b,
      selectionEnd: CellIds.b,
      selected: new Set([CellIds.b]),
    });
  });

  it("should clear selection", () => {
    // First select some cells
    actions.select({ cellId: CellIds.a });
    expect(state.selected.size).toBe(1);

    // Then clear
    actions.clear();

    expect(state).toEqual({
      selectionStart: null,
      selectionEnd: null,
      selected: new Set(),
    });
  });

  it("should handle clearing already empty selection", () => {
    // Clear when already empty
    actions.clear();

    expect(state).toEqual({
      selectionStart: null,
      selectionEnd: null,
      selected: new Set(),
    });
  });

  it("should handle complex selection scenarios", () => {
    const allCellIds = MultiColumn.from([
      [CellIds.a, CellIds.b, CellIds.c, CellIds.d, CellIds.e],
    ]);

    // Select middle cell
    actions.select({ cellId: CellIds.c });

    // Extend to end
    actions.extend({ cellId: CellIds.e, allCellIds });
    expect(state.selected).toEqual(new Set([CellIds.c, CellIds.d, CellIds.e]));

    // Extend to beginning (should reverse)
    actions.extend({ cellId: CellIds.a, allCellIds });
    expect(state.selected).toEqual(new Set([CellIds.a, CellIds.b, CellIds.c]));
    expect(state.selectionStart).toBe(CellIds.c);
    expect(state.selectionEnd).toBe(CellIds.a);

    // Clear everything
    actions.clear();
    expect(state.selected.size).toBe(0);
  });
});
