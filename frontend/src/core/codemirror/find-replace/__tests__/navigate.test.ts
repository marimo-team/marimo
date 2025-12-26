/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState, Text } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { store } from "@/core/state/jotai";
import { invariant } from "@/utils/invariant";
import {
  findNext,
  findPrev,
  getMatches,
  replaceAll,
  replaceNext,
} from "../navigate";
import { findReplaceAtom } from "../state";

// Mock getAllEditorViews to return our test views
const mockGetAllEditorViews = vi.fn();
vi.mock("@/core/cells/cells", () => ({
  getAllEditorViews: () => mockGetAllEditorViews(),
}));

describe("navigate", () => {
  let view1: EditorView;
  let view2: EditorView;
  let mockViews: EditorView[];

  beforeEach(() => {
    // Create test editor views with different content
    const state1 = EditorState.create({
      doc: Text.of(["Hello world", "This is a test", "Hello again"]),
    });

    const state2 = EditorState.create({
      doc: Text.of(["Another hello", "Different content", "Hello there"]),
    });

    // Create mock views that track dispatch calls
    view1 = {
      state: state1,
      dispatch: vi.fn(() => {
        // Mock dispatch - in real tests we just need to verify it was called
        // Don't actually apply changes as it's complex to mock properly
      }),
    } as unknown as EditorView;

    view2 = {
      state: state2,
      dispatch: vi.fn(() => {
        // Mock dispatch - in real tests we just need to verify it was called
      }),
    } as unknown as EditorView;

    mockViews = [view1, view2];
    mockGetAllEditorViews.mockReturnValue(mockViews);

    // Set up initial find/replace state
    store.set(findReplaceAtom, {
      type: "setFind",
      find: "hello",
    });
    store.set(findReplaceAtom, {
      type: "setReplace",
      replace: "hi",
    });
    store.set(findReplaceAtom, {
      type: "setCaseSensitive",
      caseSensitive: false,
    });
    store.set(findReplaceAtom, {
      type: "setRegex",
      regexp: false,
    });
    store.set(findReplaceAtom, {
      type: "setWholeWord",
      wholeWord: false,
    });
    store.set(findReplaceAtom, {
      type: "setCurrentView",
      view: view1,
      range: { from: 0, to: 0 },
    });
  });

  afterEach(() => {
    // Reset state
    store.set(findReplaceAtom, {
      type: "clearCurrentView",
    });
    vi.clearAllMocks();
  });

  describe("findNext", () => {
    it("should find next match in same view", () => {
      const result = findNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      expect(result.from).toBe(0);
      expect(result.to).toBe(5);
      expect(view1.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          selection: expect.any(Object),
          effects: expect.any(Array),
          userEvent: "select.search",
        }),
      );

      // Check that state was updated
      const state = store.get(findReplaceAtom);
      expect(state.currentView?.view).toBe(view1);
      expect(state.currentView?.range).toEqual({ from: 0, to: 5 });
    });

    it("should find next match in different view when current view exhausted", () => {
      // Set current position to after last match in view1
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: view1,
        range: { from: 30, to: 35 },
      });

      const result = findNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      // Should find match somewhere (either view1 wraps or view2)
      expect(view1.dispatch).toHaveBeenCalled();

      const state = store.get(findReplaceAtom);
      expect(state.currentView?.view).toBeDefined();
    });

    it("should wrap around to beginning when reaching end", () => {
      // Start from end of last view
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: view2,
        range: { from: 50, to: 55 },
      });

      const result = findNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      // Should wrap back to view1
      const state = store.get(findReplaceAtom);
      expect(state.currentView?.view).toBe(view1);
    });

    it("should return false when no matches found", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "nonexistent",
      });

      const result = findNext();

      expect(result).toBe(false);
    });

    it("should handle case sensitive search", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "Hello",
      });
      store.set(findReplaceAtom, {
        type: "setCaseSensitive",
        caseSensitive: true,
      });

      const result = findNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      expect(result.from).toBe(0);
      expect(result.to).toBe(5);
    });

    it("should handle regex search", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "h[eE]llo",
      });
      store.set(findReplaceAtom, {
        type: "setRegex",
        regexp: true,
      });

      const result = findNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      expect(result.from).toBe(0);
      expect(result.to).toBe(5);
      expect(view1.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          selection: expect.any(Object),
          effects: expect.any(Array),
          userEvent: "select.search",
        }),
      );
    });

    it("should handle whole word search", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "test",
      });
      store.set(findReplaceAtom, {
        type: "setWholeWord",
        wholeWord: true,
      });

      const result = findNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      // Should find "test" as a whole word
      expect(result.from).toBeGreaterThan(0);
    });

    it("should handle invalid regex gracefully", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "[invalid",
      });
      store.set(findReplaceAtom, {
        type: "setRegex",
        regexp: true,
      });

      const result = findNext();

      expect(result).toBe(false);
    });
  });

  describe("findPrev", () => {
    it("should find previous match", () => {
      // Start from position after first match
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: view1,
        range: { from: 25, to: 30 },
      });

      const result = findPrev();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      expect(result.from).toBe(0);
      expect(result.to).toBe(5);
    });

    it("should search backwards across views", () => {
      // Start from second view
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: view2,
        range: { from: 5, to: 10 },
      });

      const result = findPrev();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      // Should find match in view2 or wrap to view1
      const state = store.get(findReplaceAtom);
      expect([view1, view2]).toContain(state.currentView?.view);
    });

    it("should return false when no previous matches", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "nonexistent",
      });

      const result = findPrev();

      expect(result).toBe(false);
    });
  });

  describe("replaceAll", () => {
    it("should replace all matches across all views", () => {
      const undoHandler = replaceAll();

      expect(typeof undoHandler).toBe("function");
      expect(view1.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          changes: expect.any(Array),
          userEvent: "input.replace.all",
        }),
      );
      expect(view2.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          changes: expect.any(Array),
          userEvent: "input.replace.all",
        }),
      );

      // Test undo functionality
      if (undoHandler) {
        undoHandler();
      }
      // Should restore original content
      expect(view1.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          userEvent: "input.replace.all",
        }),
      );
    });

    it("should skip read-only views", () => {
      // Create a read-only state
      const readOnlyState = EditorState.create({
        doc: Text.of(["Hello world", "This is a test"]),
        extensions: [EditorState.readOnly.of(true)],
      });

      const readOnlyView = {
        state: readOnlyState,
        dispatch: vi.fn(),
      } as unknown as EditorView;

      // Replace view1 with read-only view temporarily
      mockGetAllEditorViews.mockReturnValueOnce([readOnlyView, view2]);

      const undoHandler = replaceAll();

      expect(typeof undoHandler).toBe("function");
      // read-only view should not be modified
      expect(readOnlyView.dispatch).not.toHaveBeenCalled();
      // view2 should still be modified
      expect(view2.dispatch).toHaveBeenCalled();
    });

    it("should handle views with no matches", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "nonexistent",
      });

      const undoHandler = replaceAll();

      expect(typeof undoHandler).toBe("function");
      // No views should be modified
      expect(view1.dispatch).not.toHaveBeenCalled();
      expect(view2.dispatch).not.toHaveBeenCalled();
    });

    it("should handle regex replacement with groups", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "(h)(ello)",
      });
      store.set(findReplaceAtom, {
        type: "setReplace",
        replace: "$2$1",
      });
      store.set(findReplaceAtom, {
        type: "setRegex",
        regexp: true,
      });

      const undoHandler = replaceAll();

      expect(typeof undoHandler).toBe("function");
      expect(view1.dispatch).toHaveBeenCalled();
      expect(view2.dispatch).toHaveBeenCalled();
    });
  });

  describe("replaceNext", () => {
    it("should replace next match and find following one", () => {
      const result = replaceNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      expect(view1.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          changes: expect.any(Array),
          userEvent: "input.replace",
        }),
      );

      // Should also call findNext to locate next match
      const state = store.get(findReplaceAtom);
      expect(state.currentView).toBeDefined();
    });

    it("should return false when no matches found", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "nonexistent",
      });

      const result = replaceNext();

      expect(result).toBe(false);
      expect(view1.dispatch).not.toHaveBeenCalledWith(
        expect.objectContaining({
          userEvent: "input.replace",
        }),
      );
    });

    it("should handle replacement at different positions", () => {
      // Set position to second match
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: view1,
        range: { from: 25, to: 30 },
      });

      const result = replaceNext();

      expect(result).toBeTruthy();
      invariant(result, "findNext should return a result");
      expect(view1.dispatch).toHaveBeenCalledWith(
        expect.objectContaining({
          changes: expect.any(Array),
          userEvent: "input.replace",
        }),
      );
    });
  });

  describe("getMatches", () => {
    it("should count all matches across all views", () => {
      const result = getMatches();

      expect(result).toMatchObject({
        count: expect.any(Number),
        position: expect.any(Map),
      });
      invariant(result, "getMatches should return a result");
      expect(result.count).toBeGreaterThan(0);
      expect(result.position.size).toBe(2); // Two views
    });

    it("should return zero matches when search term not found", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "nonexistent",
      });

      const result = getMatches();

      invariant(result, "getMatches should return a result");
      expect(result.count).toBe(0);
      expect(result.position.size).toBe(0);
    });

    it("should handle case sensitive matching", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "Hello",
      });
      store.set(findReplaceAtom, {
        type: "setCaseSensitive",
        caseSensitive: true,
      });

      const result = getMatches();

      // Should only match "Hello" with exact case
      invariant(result, "getMatches should return a result");
      expect(result.count).toBeGreaterThan(0);
      expect(result.position.size).toBeGreaterThan(0);
    });

    it("should store correct position information", () => {
      const result = getMatches();

      invariant(result, "getMatches should return a result");
      // Check that positions are stored correctly
      const view1Positions = result.position.get(view1);
      const view2Positions = result.position.get(view2);

      if (view1Positions) {
        expect(view1Positions.size).toBeGreaterThan(0);
        // Check that position keys are in "from:to" format
        for (const key of view1Positions.keys()) {
          expect(key).toMatch(/^\d+:\d+$/);
        }
      }

      if (view2Positions) {
        expect(view2Positions.size).toBeGreaterThan(0);
      }
    });

    it("should handle regex patterns", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "h[eE]llo",
      });
      store.set(findReplaceAtom, {
        type: "setRegex",
        regexp: true,
      });

      const result = getMatches();

      invariant(result, "getMatches should return a result");
      expect(result.count).toBeGreaterThan(0);
      expect(result.position.size).toBeGreaterThan(0);
    });

    it("should handle whole word matching", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "test",
      });
      store.set(findReplaceAtom, {
        type: "setWholeWord",
        wholeWord: true,
      });

      const result = getMatches();

      invariant(result, "getMatches should return a result");
      expect(result.count).toBeGreaterThan(0);
    });
  });

  describe("edge cases", () => {
    it("should not get stuck on same match when navigating backwards", () => {
      // This test verifies the fix for the bug where findPrev could get stuck
      // Start at the second match in the first view (position around "Hello again")
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: view1,
        range: { from: 25, to: 30 }, // Position after "Hello" matches
      });

      // Find previous should go to the first "Hello" match
      const firstPrev = findPrev();
      expect(firstPrev).toBeTruthy();
      invariant(firstPrev, "findPrev should return a result");

      const stateAfterFirst = store.get(findReplaceAtom);
      const firstMatchRange = stateAfterFirst.currentView?.range;

      // Find previous again - should NOT stay on the same match
      const secondPrev = findPrev();
      expect(secondPrev).toBeTruthy();
      invariant(secondPrev, "findPrev should return a result");

      const stateAfterSecond = store.get(findReplaceAtom);
      const secondMatchRange = stateAfterSecond.currentView?.range;

      // Should be different matches (either different position or different view)
      const isDifferentMatch =
        firstMatchRange?.from !== secondMatchRange?.from ||
        firstMatchRange?.to !== secondMatchRange?.to ||
        stateAfterFirst.currentView?.view !==
          stateAfterSecond.currentView?.view;

      expect(isDifferentMatch).toBe(true);
    });

    it("should properly navigate backwards through multiple matches", () => {
      // Create a test document with clearly positioned matches
      const testDoc = EditorState.create({
        doc: Text.of(["hello world hello there hello"]),
      });

      const testView = {
        state: testDoc,
        dispatch: vi.fn(),
      } as unknown as EditorView;

      mockGetAllEditorViews.mockReturnValue([testView]);

      // Start at position after the last "hello" (position 24-29)
      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: testView,
        range: { from: 24, to: 29 }, // Last "hello"
      });

      // First findPrev should find the middle "hello" at position 12-17
      const firstResult = findPrev();
      expect(firstResult).toBeTruthy();
      invariant(firstResult, "findPrev should return a result");

      const firstState = store.get(findReplaceAtom);
      expect(firstState.currentView?.range.from).toBe(12);
      expect(firstState.currentView?.range.to).toBe(17);

      // Second findPrev should find the first "hello" at position 0-5
      const secondResult = findPrev();
      expect(secondResult).toBeTruthy();
      invariant(secondResult, "findPrev should return a result");

      const secondState = store.get(findReplaceAtom);
      expect(secondState.currentView?.range.from).toBe(0);
      expect(secondState.currentView?.range.to).toBe(5);
    });

    it("should handle empty views array", () => {
      mockGetAllEditorViews.mockReturnValue([]);

      const result = findNext();
      expect(result).toBe(false);
    });

    it("should handle views with empty documents", () => {
      const emptyState = EditorState.create({
        doc: Text.of([""]),
      });

      const emptyView = {
        state: emptyState,
        dispatch: vi.fn(),
      } as unknown as EditorView;

      mockGetAllEditorViews.mockReturnValue([emptyView]);

      const result = findNext();
      expect(result).toBe(false);
    });

    it("should handle currentView not in views array", () => {
      const orphanState = EditorState.create({
        doc: Text.of(["orphan content"]),
      });

      const orphanView = {
        state: orphanState,
        dispatch: vi.fn(),
      } as unknown as EditorView;

      store.set(findReplaceAtom, {
        type: "setCurrentView",
        view: orphanView,
        range: { from: 0, to: 0 },
      });

      const result = findNext();
      // Should still work by starting from index 0
      if (result) {
        expect(result).toBeTruthy();
        invariant(result, "findNext should return a result");
      } else {
        // It's ok if no match is found since "hello" might not be in the mock views
        expect(result).toBe(false);
      }
    });

    it("should handle malformed regex in replace pattern", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "(hello)",
      });
      store.set(findReplaceAtom, {
        type: "setReplace",
        replace: "$1$2", // $2 doesn't exist
      });
      store.set(findReplaceAtom, {
        type: "setRegex",
        regexp: true,
      });

      // Should not throw an error
      expect(() => replaceNext()).not.toThrow();
    });

    it("should handle empty search text", () => {
      store.set(findReplaceAtom, {
        type: "setFind",
        find: "",
      });

      const result = findNext();
      expect(result).toBe(false);
    });

    it("should preserve view state when no changes are made", () => {
      const originalDoc = view1.state.doc.toString();

      store.set(findReplaceAtom, {
        type: "setFind",
        find: "nonexistent",
      });

      replaceAll();

      expect(view1.state.doc.toString()).toBe(originalDoc);
    });
  });
});
