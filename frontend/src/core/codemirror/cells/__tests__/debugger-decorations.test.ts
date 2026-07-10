/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellId } from "@/core/cells/ids";
import { createMockObservable } from "@/core/state/__mocks__/mocks";
import type { Observable } from "@/core/state/observable";
import {
  breakpointGutter,
  debuggerLineHighlighter,
} from "../debugger-decorations";

vi.mock("../debugger-state", () => ({
  toggleBreakpoint: vi.fn(),
}));

import { toggleBreakpoint } from "../debugger-state";

const CODE = `def my_function():
    x = 1
    y = 2
    return x + y

result = my_function()`;

function createLineHighlighterEditor(
  lineObservable: Observable<number | null>,
) {
  const state = EditorState.create({
    doc: CODE,
    extensions: [python(), debuggerLineHighlighter(lineObservable)],
  });
  return new EditorView({ state, parent: document.body });
}

function createBreakpointGutterEditor(
  cid: CellId,
  breakpointsObservable: Observable<ReadonlySet<number>>,
) {
  const state = EditorState.create({
    doc: CODE,
    extensions: [python(), breakpointGutter(cid, breakpointsObservable)],
  });
  return new EditorView({ state, parent: document.body });
}

/** Flush the microtask queue and apply the resulting state changes to `view`. */
async function flush(view: EditorView): Promise<void> {
  await Promise.resolve();
  view.dispatch({});
}

/**
 * Count rendered breakpoint markers, excluding the always-present hidden
 * spacer element (`initialSpacer`) that isn't an actual breakpoint.
 */
function visibleMarkerCount(view: EditorView): number {
  const gutterElement = view.dom.querySelector(".cm-breakpoint-gutter");
  if (!gutterElement) {
    return 0;
  }
  return gutterElement.querySelectorAll(
    '.cm-gutterElement:not([style*="visibility: hidden"]) .cm-breakpoint-marker',
  ).length;
}

describe("debugger-decorations", () => {
  let view: EditorView | null = null;

  afterEach(() => {
    if (view) {
      view.destroy();
      view = null;
    }
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  describe("debuggerLineHighlighter", () => {
    it("renders no highlight when the observable starts null", () => {
      const lineObservable = createMockObservable<number | null>(null);
      view = createLineHighlighterEditor(lineObservable);

      expect(view.dom.querySelector(".cm-debugger-current-line")).toBeNull();
    });

    it("highlights the line reported by the observable", () => {
      const lineObservable = createMockObservable<number | null>(null);
      view = createLineHighlighterEditor(lineObservable);

      lineObservable.set(2);
      view.dispatch({});

      expect(
        view.dom.querySelector(".cm-debugger-current-line"),
      ).not.toBeNull();
    });

    it("clears the highlight when the line is set back to null", () => {
      const lineObservable = createMockObservable<number | null>(2);
      view = createLineHighlighterEditor(lineObservable);
      view.dispatch({});
      expect(
        view.dom.querySelector(".cm-debugger-current-line"),
      ).not.toBeNull();

      lineObservable.set(null);
      view.dispatch({});

      expect(view.dom.querySelector(".cm-debugger-current-line")).toBeNull();
    });

    it("does not throw for an out-of-range line", () => {
      const lineObservable = createMockObservable<number | null>(null);
      view = createLineHighlighterEditor(lineObservable);

      expect(() => {
        lineObservable.set(9999);
        view?.dispatch({});
      }).not.toThrow();
      expect(view.dom.querySelector(".cm-debugger-current-line")).toBeNull();
    });
  });

  describe("breakpointGutter", () => {
    it("renders no markers when there are no breakpoints", () => {
      const cid = cellId("cell1");
      const breakpointsObservable = createMockObservable<ReadonlySet<number>>(
        new Set(),
      );
      view = createBreakpointGutterEditor(cid, breakpointsObservable);

      expect(visibleMarkerCount(view)).toBe(0);
    });

    it("syncs pre-existing breakpoints on mount", async () => {
      const cid = cellId("cell1");
      const breakpointsObservable = createMockObservable<ReadonlySet<number>>(
        new Set([2]),
      );
      view = createBreakpointGutterEditor(cid, breakpointsObservable);
      await flush(view); // initial sync is deferred to a microtask

      expect(visibleMarkerCount(view)).toBe(1);
    });

    it("adds a marker when the observable reports a new breakpoint", () => {
      const cid = cellId("cell1");
      const breakpointsObservable = createMockObservable<ReadonlySet<number>>(
        new Set(),
      );
      view = createBreakpointGutterEditor(cid, breakpointsObservable);

      breakpointsObservable.set(new Set([1, 3]));
      view.dispatch({});

      expect(visibleMarkerCount(view)).toBe(2);
    });

    it("toggles a breakpoint when an existing marker is clicked", async () => {
      const cid = cellId("cell1");
      // A single breakpoint on line 1 renders exactly one non-spacer
      // gutter element, so the click lands unambiguously on that line.
      const breakpointsObservable = createMockObservable<ReadonlySet<number>>(
        new Set([1]),
      );
      view = createBreakpointGutterEditor(cid, breakpointsObservable);
      await flush(view);

      const gutterElement = view.dom.querySelector(".cm-breakpoint-gutter");
      const lineElement = gutterElement?.querySelector(
        '.cm-gutterElement:not([style*="visibility: hidden"])',
      );
      expect(lineElement).not.toBeNull();
      lineElement?.dispatchEvent(
        new MouseEvent("mousedown", { bubbles: true }),
      );

      expect(toggleBreakpoint).toHaveBeenCalledWith(cid, 1);
    });
  });
});
