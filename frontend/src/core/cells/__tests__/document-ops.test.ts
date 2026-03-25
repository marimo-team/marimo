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
function resolve(
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
    state = dispatch(state, {
      type: "createNewCell",
      payload: {
        cellId: "__end__",
        before: false,
        code,
        newCellId: CellId.create(),
      },
    });
  }
}

describe("toDocumentOps", () => {
  describe("anchorOf edge cases", () => {
    it("uses before anchor when new cell is first", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = resolve(state, {
        type: "createNewCell",
        payload: {
          cellId: a,
          before: true,
          code: "first",
          newCellId: CellId.create(),
        },
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "before": "0",
            "cellId": "1",
            "code": "first",
            "config": {
              "column": null,
              "disabled": false,
              "hide_code": false,
            },
            "name": "_",
            "type": "create-cell",
          },
        ]
      `);
    });

    it("uses after anchor for __end__ insertion", () => {
      setup("a");
      const { ops } = resolve(state, {
        type: "createNewCell",
        payload: {
          cellId: "__end__",
          before: false,
          code: "last",
          newCellId: CellId.create(),
        },
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "after": "0",
            "cellId": "1",
            "code": "last",
            "config": {
              "column": null,
              "disabled": false,
              "hide_code": false,
            },
            "name": "_",
            "type": "create-cell",
          },
        ]
      `);
    });

    it("uses before when sendToTop moves cell to first position", () => {
      setup("a", "b", "c");
      const [, b] = state.cellIds.inOrderIds;

      const { ops } = resolve(state, {
        type: "sendToTop",
        payload: { cellId: b },
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "before": "0",
            "cellId": "1",
            "type": "move-cell",
          },
        ]
      `);
    });
  });

  describe("field name mapping", () => {
    it("maps hide_code to hideCode in set-config", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { ops } = resolve(state, {
        type: "updateCellConfig",
        payload: { cellId: a, config: { hide_code: true } },
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "cellId": "0",
            "hideCode": true,
            "type": "set-config",
          },
        ]
      `);
    });

    it("includes full CellConfig in create-cell", () => {
      setup("a");

      const { ops } = resolve(state, {
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
    it("dropOverNewColumn emits set-config + reorder-cells", () => {
      setup("a", "b");
      const [, b] = state.cellIds.inOrderIds;

      const { ops } = resolve(state, {
        type: "dropOverNewColumn",
        payload: { cellId: b },
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "cellId": "1",
            "column": 1,
            "type": "set-config",
          },
          {
            "cellIds": [
              "0",
              "1",
            ],
            "type": "reorder-cells",
          },
        ]
      `);
    });

    it("addColumnBreakpoint emits set-config + reorder-cells", () => {
      setup("a", "b", "c");
      const [, b] = state.cellIds.inOrderIds;

      const { ops } = resolve(state, {
        type: "addColumnBreakpoint",
        payload: { cellId: b },
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "cellId": "1",
            "column": 1,
            "type": "set-config",
          },
          {
            "cellId": "2",
            "column": 1,
            "type": "set-config",
          },
          {
            "cellIds": [
              "0",
              "1",
              "2",
            ],
            "type": "reorder-cells",
          },
        ]
      `);
    });

    it("mergeAllColumns emits set-config + reorder-cells", () => {
      setup("a", "b", "c");
      const [, b] = state.cellIds.inOrderIds;
      state = dispatch(state, {
        type: "addColumnBreakpoint",
        payload: { cellId: b },
      });

      const { ops } = resolve(state, {
        type: "mergeAllColumns",
        payload: {},
      });

      expect(ops).toMatchInlineSnapshot(`
        [
          {
            "cellId": "1",
            "column": 0,
            "type": "set-config",
          },
          {
            "cellId": "2",
            "column": 0,
            "type": "set-config",
          },
          {
            "cellIds": [
              "0",
              "1",
              "2",
            ],
            "type": "reorder-cells",
          },
        ]
      `);
    });
  });

  describe("actions that should NOT emit ops", () => {
    it("focusCell returns empty", () => {
      setup("a", "b");
      const [a] = state.cellIds.inOrderIds;
      const { ops } = resolve(state, {
        type: "focusCell",
        payload: { cellId: a, where: "after" },
      });
      expect(ops).toHaveLength(0);
    });

    it("prepareForRun returns empty", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;
      const { ops } = resolve(state, {
        type: "prepareForRun",
        payload: { cellId: a },
      });
      expect(ops).toHaveLength(0);
    });
  });
});
