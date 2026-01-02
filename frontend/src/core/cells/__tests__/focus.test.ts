/* Copyright 2026 Marimo. All rights reserved. */
import { beforeEach, describe, expect, it } from "vitest";
import type { CellId } from "@/core/cells/ids";
import type { CellFocusState } from "../focus";
import { exportedForTesting } from "../focus";

const { initialState, reducer, createActions } = exportedForTesting;

const CellIds = {
  a: "a" as CellId,
  b: "b" as CellId,
  c: "c" as CellId,
};

describe("cell focus reducer", () => {
  let state: CellFocusState;

  const actions = createActions((action) => {
    state = reducer(state, action);
  });

  beforeEach(() => {
    state = initialState();
  });

  it("should have initial state", () => {
    expect(state).toEqual({
      focusedCellId: null,
      lastFocusedCellId: null,
    });
  });

  describe("focusCell", () => {
    it("should focus a cell from initial state", () => {
      actions.focusCell({ cellId: CellIds.a });

      expect(state).toEqual({
        focusedCellId: CellIds.a,
        lastFocusedCellId: CellIds.a,
      });
    });

    it("should change focus to a different cell", () => {
      // First focus cell a
      actions.focusCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Then focus cell b
      actions.focusCell({ cellId: CellIds.b });

      expect(state).toEqual({
        focusedCellId: CellIds.b,
        lastFocusedCellId: CellIds.b,
      });
    });

    it("should maintain both focus and last focus when focusing same cell", () => {
      // Focus cell a
      actions.focusCell({ cellId: CellIds.a });

      // Focus same cell again
      actions.focusCell({ cellId: CellIds.a });

      expect(state).toEqual({
        focusedCellId: CellIds.a,
        lastFocusedCellId: CellIds.a,
      });
    });

    it("should preserve last focused cell when focusing different cells", () => {
      // Focus cell a
      actions.focusCell({ cellId: CellIds.a });

      // Focus cell b
      actions.focusCell({ cellId: CellIds.b });

      // Focus cell c
      actions.focusCell({ cellId: CellIds.c });

      expect(state).toEqual({
        focusedCellId: CellIds.c,
        lastFocusedCellId: CellIds.c,
      });
    });
  });

  describe("toggleCell", () => {
    it("should focus a cell when none is focused", () => {
      actions.toggleCell({ cellId: CellIds.a });

      expect(state).toEqual({
        focusedCellId: CellIds.a,
        lastFocusedCellId: CellIds.a,
      });
    });

    it("should blur a cell when it is already focused", () => {
      // First focus a cell
      actions.focusCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Toggle the same cell should blur it
      actions.toggleCell({ cellId: CellIds.a });

      expect(state).toEqual({
        focusedCellId: null,
        lastFocusedCellId: CellIds.a, // last focused should remain
      });
    });

    it("should switch focus when toggling a different cell", () => {
      // First focus cell a
      actions.focusCell({ cellId: CellIds.a });

      // Toggle cell b should switch focus
      actions.toggleCell({ cellId: CellIds.b });

      expect(state).toEqual({
        focusedCellId: CellIds.b,
        lastFocusedCellId: CellIds.b,
      });
    });

    it("should handle multiple toggles correctly", () => {
      // Toggle cell a (focus it)
      actions.toggleCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Toggle cell a again (blur it)
      actions.toggleCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(null);
      expect(state.lastFocusedCellId).toBe(CellIds.a);

      // Toggle cell a again (focus it)
      actions.toggleCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);
      expect(state.lastFocusedCellId).toBe(CellIds.a);
    });

    it("should toggle between different cells", () => {
      // Toggle cell a
      actions.toggleCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Toggle cell b
      actions.toggleCell({ cellId: CellIds.b });
      expect(state.focusedCellId).toBe(CellIds.b);
      expect(state.lastFocusedCellId).toBe(CellIds.b);

      // Toggle cell c
      actions.toggleCell({ cellId: CellIds.c });
      expect(state.focusedCellId).toBe(CellIds.c);
      expect(state.lastFocusedCellId).toBe(CellIds.c);

      // Toggle cell c again (blur it)
      actions.toggleCell({ cellId: CellIds.c });
      expect(state.focusedCellId).toBe(null);
      expect(state.lastFocusedCellId).toBe(CellIds.c);
    });
  });

  describe("blurCell", () => {
    it("should blur focused cell", () => {
      // First focus a cell
      actions.focusCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Blur it
      actions.blurCell();

      expect(state).toEqual({
        focusedCellId: null,
        lastFocusedCellId: CellIds.a, // last focused should remain
      });
    });

    it("should handle blurring when no cell is focused", () => {
      // Blur when nothing is focused
      actions.blurCell();

      expect(state).toEqual({
        focusedCellId: null,
        lastFocusedCellId: null,
      });
    });

    it("should preserve last focused cell when blurring", () => {
      // Focus cell a, then cell b
      actions.focusCell({ cellId: CellIds.a });
      actions.focusCell({ cellId: CellIds.b });

      // Blur
      actions.blurCell();

      expect(state).toEqual({
        focusedCellId: null,
        lastFocusedCellId: CellIds.b,
      });
    });

    it("should handle multiple blur calls", () => {
      // Focus and blur
      actions.focusCell({ cellId: CellIds.a });
      actions.blurCell();

      const firstBlurState = { ...state };

      // Blur again
      actions.blurCell();

      // Should remain the same
      expect(state).toEqual(firstBlurState);
    });
  });

  describe("complex scenarios", () => {
    it("should handle focus -> blur -> toggle sequence", () => {
      // Focus cell a
      actions.focusCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Blur it
      actions.blurCell();
      expect(state.focusedCellId).toBe(null);
      expect(state.lastFocusedCellId).toBe(CellIds.a);

      // Toggle cell a (should focus it)
      actions.toggleCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);
      expect(state.lastFocusedCellId).toBe(CellIds.a);
    });

    it("should handle toggle -> focus -> blur sequence", () => {
      // Toggle cell a (focus it)
      actions.toggleCell({ cellId: CellIds.a });
      expect(state.focusedCellId).toBe(CellIds.a);

      // Focus cell b
      actions.focusCell({ cellId: CellIds.b });
      expect(state.focusedCellId).toBe(CellIds.b);

      // Blur
      actions.blurCell();
      expect(state.focusedCellId).toBe(null);
      expect(state.lastFocusedCellId).toBe(CellIds.b);
    });

    it("should handle mixed operations maintaining last focused", () => {
      // Focus a
      actions.focusCell({ cellId: CellIds.a });

      // Toggle b (switch focus)
      actions.toggleCell({ cellId: CellIds.b });
      expect(state.lastFocusedCellId).toBe(CellIds.b);

      // Toggle b again (blur)
      actions.toggleCell({ cellId: CellIds.b });
      expect(state.focusedCellId).toBe(null);
      expect(state.lastFocusedCellId).toBe(CellIds.b);

      // Focus c
      actions.focusCell({ cellId: CellIds.c });
      expect(state.lastFocusedCellId).toBe(CellIds.c);

      // Blur
      actions.blurCell();
      expect(state.focusedCellId).toBe(null);
      expect(state.lastFocusedCellId).toBe(CellIds.c);
    });
  });
});
