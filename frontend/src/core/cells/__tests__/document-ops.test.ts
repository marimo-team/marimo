/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Tests for toDocumentOps (action → op mapping) as a pure function.
 *
 * Each test calls the reducer to produce prevState/newState, then calls
 * toDocumentOps directly — no middleware, no side effects. Basic round-trip
 * correctness is covered by document-roundtrip.test.ts. This file focuses on:
 *
 * - anchorOf edge cases (before vs after, first cell, __end__)
 * - Field name mapping (hide_code → hideCode)
 * - Column structure actions emitting reorder-cells
 * - Actions that should NOT emit ops
 */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterAll, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { MultiColumn } from "@/utils/id-tree";
import { exportedForTesting, type NotebookState } from "../cells";
import { toDocumentOps } from "../document-ops";
import { CellId } from "../ids";

const { initialNotebookState, reducer } = exportedForTesting;

function createEditor(code: string) {
  const state = EditorState.create({
    doc: code,
    extensions: [
      python(),
      adaptiveLanguageConfiguration({
        cellId: cellId("cell1"),
        completionConfig: {
          activate_on_typing: true,
          signature_hint_on_typing: false,
          copilot: false,
          codeium_api_key: null,
        },
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
        lspConfig: {},
      }),
    ],
  });
  return new EditorView({ state, parent: document.body });
}

/** Dispatch an action through the reducer and auto-create editor handles. */
function dispatch(
  state: NotebookState,
  action: { type: string; payload: unknown },
): NotebookState {
  const next = reducer(state, action);
  for (const [cellIdString, handle] of Object.entries(next.cellHandles)) {
    const cid = cellIdString as CellId;
    if (!handle.current) {
      const view = createEditor(next.cellData[cid].code);
      const h: CellHandle = { editorView: view, editorViewOrNull: view };
      next.cellHandles[cid] = { current: h };
    }
  }
  return next;
}

/** Dispatch an action and return the ops it produces. */
function dispatchAndResolve(
  state: NotebookState,
  action: { type: string; payload: unknown },
) {
  const next = dispatch(state, action);
  const ops = toDocumentOps(state, next, action as any);
  return { next, ops };
}

let state: NotebookState;

let i = 0;
const originalCreate = CellId.create.bind(CellId);

beforeAll(() => {
  CellId.create = () => cellId(`${i++}`);
});

beforeEach(() => {
  i = 0;
  state = initialNotebookState();
  state.cellIds = MultiColumn.from([]);
});

afterAll(() => {
  CellId.create = originalCreate;
});

function setup(...codes: string[]) {
  for (const code of codes) {
    const action = {
      type: "createNewCell",
      payload: {
        cellId: "__end__",
        before: false,
        code,
        newCellId: CellId.create(),
      },
    };
    state = dispatch(state, action);
  }
}

describe("toDocumentOps", () => {
  describe("anchorOf edge cases", () => {
    it("uses before anchor when new cell is first", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "createNewCell",
        payload: {
          cellId: a,
          before: true,
          code: "first",
          newCellId: CellId.create(),
        },
      });

      expect(ops).toHaveLength(1);
      expect(ops[0]).toMatchObject({ type: "create-cell", before: a });
      expect(ops[0]).not.toHaveProperty("after");
    });

    it("uses after anchor for __end__ insertion", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "createNewCell",
        payload: {
          cellId: "__end__",
          before: false,
          code: "last",
          newCellId: CellId.create(),
        },
      });

      expect(ops[0]).toMatchObject({ after: a });
    });

    it("uses before when sendToTop moves cell to first position", () => {
      setup("a", "b", "c");
      const [, b] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "sendToTop",
        payload: { cellId: b },
      });

      expect(ops[0]).toMatchObject({ type: "move-cell", cellId: b });
      expect(ops[0]).toHaveProperty("before");
      expect(ops[0]).not.toHaveProperty("after");
    });
  });

  describe("field name mapping", () => {
    it("maps hide_code to hideCode in set-config", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "updateCellConfig",
        payload: { cellId: a, config: { hide_code: true } },
      });

      expect(ops[0]).toEqual({
        type: "set-config",
        cellId: a,
        hideCode: true,
      });
    });

    it("includes full CellConfig in create-cell", () => {
      setup("a");

      const { ops } = dispatchAndResolve(state, {
        type: "createNewCell",
        payload: {
          cellId: "__end__",
          before: false,
          code: "hidden",
          newCellId: CellId.create(),
          hideCode: true,
        },
      });

      expect(ops[0]).toMatchObject({
        type: "create-cell",
        config: { hide_code: true },
      });
    });
  });

  describe("column structure actions", () => {
    it("dropOverNewColumn emits reorder-cells", () => {
      setup("a", "b");
      const [, b] = state.cellIds.inOrderIds;

      const { ops, next } = dispatchAndResolve(state, {
        type: "dropOverNewColumn",
        payload: { cellId: b },
      });

      expect(ops).toHaveLength(1);
      expect(ops[0]).toMatchObject({ type: "reorder-cells" });
      expect((ops[0] as any).cellIds).toEqual(next.cellIds.inOrderIds);
    });

    it("addColumnBreakpoint emits reorder-cells", () => {
      setup("a", "b", "c");
      const [, b] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "addColumnBreakpoint",
        payload: { cellId: b },
      });

      expect(ops).toHaveLength(1);
      expect(ops[0]).toMatchObject({ type: "reorder-cells" });
    });

    it("mergeAllColumns emits reorder-cells", () => {
      setup("a", "b", "c");
      const [, b] = state.cellIds.inOrderIds;
      // Create a second column first
      state = dispatch(state, {
        type: "addColumnBreakpoint",
        payload: { cellId: b },
      });

      const { ops } = dispatchAndResolve(state, {
        type: "mergeAllColumns",
        payload: {},
      });

      expect(ops).toHaveLength(1);
      expect(ops[0]).toMatchObject({ type: "reorder-cells" });
    });
  });

  describe("actions that should NOT emit ops", () => {
    it("focusCell does not emit ops", () => {
      setup("a", "b");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "focusCell",
        payload: { cellId: a, where: "after" },
      });

      expect(ops).toHaveLength(0);
    });

    it("prepareForRun does not emit ops", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = dispatchAndResolve(state, {
        type: "prepareForRun",
        payload: { cellId: a },
      });

      expect(ops).toHaveLength(0);
    });
  });
});
