/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { cellId } from "@/__tests__/branded";
import { store } from "@/core/state/jotai";
import {
  activeLineAtom,
  breakpointsAtom,
  clearCellBreakpoints,
  createActiveLineInfoAtom,
  createCellBreakpointsAtom,
  createDebuggerLineAtom,
  resyncBreakpoints,
  setActiveLine,
  toggleBreakpoint,
} from "../debugger-state";

const mockRequestClient = MockRequestClient.create();
vi.mock("@/core/network/requests", () => ({
  getRequestClient: () => mockRequestClient,
}));

const cell1 = cellId("cell1");
const cell2 = cellId("cell2");

describe("debugger-state", () => {
  beforeEach(() => {
    store.set(breakpointsAtom, new Map());
    store.set(activeLineAtom, null);
    vi.clearAllMocks();
  });

  describe("toggleBreakpoint", () => {
    it("adds a breakpoint and syncs the full set to the kernel", () => {
      toggleBreakpoint(cell1, 3);

      expect(store.get(breakpointsAtom).get(cell1)).toEqual(new Set([3]));
      expect(mockRequestClient.sendSetBreakpoints).toHaveBeenCalledWith({
        breakpoints: { [cell1]: [3] },
      });
    });

    it("removes a breakpoint on second toggle and drops the cell once empty", () => {
      toggleBreakpoint(cell1, 3);
      toggleBreakpoint(cell1, 3);

      expect(store.get(breakpointsAtom).has(cell1)).toBe(false);
      expect(mockRequestClient.sendSetBreakpoints).toHaveBeenLastCalledWith({
        breakpoints: {},
      });
    });

    it("sends lines sorted ascending for a cell with multiple breakpoints", () => {
      toggleBreakpoint(cell1, 5);
      toggleBreakpoint(cell1, 2);

      expect(mockRequestClient.sendSetBreakpoints).toHaveBeenLastCalledWith({
        breakpoints: { [cell1]: [2, 5] },
      });
    });

    it("keeps breakpoints for other cells independent", () => {
      toggleBreakpoint(cell1, 1);
      toggleBreakpoint(cell2, 2);

      expect(store.get(breakpointsAtom).get(cell1)).toEqual(new Set([1]));
      expect(store.get(breakpointsAtom).get(cell2)).toEqual(new Set([2]));
    });
  });

  describe("clearCellBreakpoints", () => {
    it("removes all breakpoints for a cell and syncs", () => {
      toggleBreakpoint(cell1, 1);
      toggleBreakpoint(cell1, 2);
      vi.clearAllMocks();

      clearCellBreakpoints(cell1);

      expect(store.get(breakpointsAtom).has(cell1)).toBe(false);
      expect(mockRequestClient.sendSetBreakpoints).toHaveBeenCalledWith({
        breakpoints: {},
      });
    });

    it("is a no-op when the cell has no breakpoints", () => {
      clearCellBreakpoints(cell1);

      expect(mockRequestClient.sendSetBreakpoints).not.toHaveBeenCalled();
    });
  });

  describe("resyncBreakpoints", () => {
    it("re-sends the current breakpoint set", () => {
      toggleBreakpoint(cell1, 4);
      vi.clearAllMocks();

      resyncBreakpoints();

      expect(mockRequestClient.sendSetBreakpoints).toHaveBeenCalledWith({
        breakpoints: { [cell1]: [4] },
      });
    });

    it("does not send when there are no breakpoints", () => {
      resyncBreakpoints();

      expect(mockRequestClient.sendSetBreakpoints).not.toHaveBeenCalled();
    });
  });

  describe("createCellBreakpointsAtom", () => {
    it("returns the empty set for a cell with no breakpoints", () => {
      const atom = createCellBreakpointsAtom(cell1);
      expect(store.get(atom)).toEqual(new Set());
    });

    it("reflects breakpoints for its own cell only", () => {
      toggleBreakpoint(cell1, 7);
      const cell1Atom = createCellBreakpointsAtom(cell1);
      const cell2Atom = createCellBreakpointsAtom(cell2);

      expect(store.get(cell1Atom)).toEqual(new Set([7]));
      expect(store.get(cell2Atom)).toEqual(new Set());
    });
  });

  describe("createDebuggerLineAtom", () => {
    it("returns null when no line is set", () => {
      const atom = createDebuggerLineAtom(cell1);
      expect(store.get(atom)).toBeNull();
    });

    it("returns the line only for the matching cell", () => {
      store.set(activeLineAtom, { cellId: cell1, line: 10, startedAtMs: 0 });

      expect(store.get(createDebuggerLineAtom(cell1))).toBe(10);
      expect(store.get(createDebuggerLineAtom(cell2))).toBeNull();
    });
  });

  describe("setActiveLine", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("stamps startedAtMs when the line is first set", () => {
      vi.setSystemTime(1000);
      setActiveLine({ cellId: cell1, line: 3 });

      expect(store.get(activeLineAtom)).toEqual({
        cellId: cell1,
        line: 3,
        startedAtMs: 1000,
      });
    });

    it("preserves startedAtMs when the same line is set again", () => {
      vi.setSystemTime(1000);
      setActiveLine({ cellId: cell1, line: 3 });
      vi.setSystemTime(2000);
      setActiveLine({ cellId: cell1, line: 3 });

      expect(store.get(activeLineAtom)?.startedAtMs).toBe(1000);
    });

    it("resets startedAtMs when the line changes", () => {
      vi.setSystemTime(1000);
      setActiveLine({ cellId: cell1, line: 3 });
      vi.setSystemTime(2000);
      setActiveLine({ cellId: cell1, line: 4 });

      expect(store.get(activeLineAtom)).toEqual({
        cellId: cell1,
        line: 4,
        startedAtMs: 2000,
      });
    });

    it("resets startedAtMs when the cell changes", () => {
      vi.setSystemTime(1000);
      setActiveLine({ cellId: cell1, line: 3 });
      vi.setSystemTime(2000);
      setActiveLine({ cellId: cell2, line: 3 });

      expect(store.get(activeLineAtom)).toEqual({
        cellId: cell2,
        line: 3,
        startedAtMs: 2000,
      });
    });

    it("clears the active line on null", () => {
      setActiveLine({ cellId: cell1, line: 3 });
      setActiveLine(null);

      expect(store.get(activeLineAtom)).toBeNull();
    });
  });

  describe("createActiveLineInfoAtom", () => {
    it("returns null when no line is set", () => {
      expect(store.get(createActiveLineInfoAtom(cell1))).toBeNull();
    });

    it("returns line info only for the matching cell", () => {
      store.set(activeLineAtom, { cellId: cell1, line: 10, startedAtMs: 42 });

      expect(store.get(createActiveLineInfoAtom(cell1))).toEqual({
        line: 10,
        startedAtMs: 42,
      });
      expect(store.get(createActiveLineInfoAtom(cell2))).toBeNull();
    });
  });
});
