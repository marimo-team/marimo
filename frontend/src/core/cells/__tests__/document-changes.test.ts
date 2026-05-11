/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Tests for toDocumentChanges (action → change mapping) as a pure function.
 *
 * Each test calls the reducer to produce prevState/newState, then calls
 * toDocumentChanges directly — no middleware, no side effects. Basic round-trip
 * correctness is covered by document-roundtrip.test.ts. This file focuses on:
 *
 * - anchorOf edge cases (before vs after, first cell, __end__)
 * - Field name mapping (hide_code → hideCode)
 * - Column structure actions emitting reorder-cells
 * - Actions that should NOT emit changes
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
import { type CellAction, toDocumentChanges } from "../document-changes";
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
function dispatch(state: NotebookState, action: CellAction): NotebookState {
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

/** Dispatch an action and return the changes it produces. */
function resolve(state: NotebookState, action: CellAction) {
  const next = dispatch(state, action);
  const changes = toDocumentChanges(state, next, action);
  return { next, changes };
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

describe("toDocumentChanges", () => {
  describe("anchorOf edge cases", () => {
    it("uses before anchor when new cell is first", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { changes } = resolve(state, {
        type: "createNewCell",
        payload: {
          cellId: a,
          before: true,
          code: "first",
          newCellId: CellId.create(),
        },
      });

      expect(changes).toMatchInlineSnapshot(`
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
      const { changes } = resolve(state, {
        type: "createNewCell",
        payload: {
          cellId: "__end__",
          before: false,
          code: "last",
          newCellId: CellId.create(),
        },
      });

      expect(changes).toMatchInlineSnapshot(`
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

      const { changes } = resolve(state, {
        type: "sendToTop",
        payload: { cellId: b },
      });

      expect(changes).toMatchInlineSnapshot(`
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

      const { changes } = resolve(state, {
        type: "updateCellConfig",
        payload: { cellId: a, config: { hide_code: true } },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "cellId": "0",
            "column": null,
            "disabled": false,
            "hideCode": true,
            "type": "set-config",
          },
        ]
      `);
    });

    it("includes full CellConfig in create-cell", () => {
      setup("a");

      const { changes } = resolve(state, {
        type: "createNewCell",
        payload: {
          cellId: "__end__",
          before: false,
          code: "hidden",
          newCellId: CellId.create(),
          hideCode: true,
        },
      });

      expect(changes[0]).toMatchObject({
        type: "create-cell",
        config: { hide_code: true },
      });
    });
  });

  describe("column structure actions", () => {
    it("dropOverNewColumn emits set-config + reorder-cells", () => {
      setup("a", "b");
      const [, b] = state.cellIds.inOrderIds;

      const { changes } = resolve(state, {
        type: "dropOverNewColumn",
        payload: { cellId: b },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "cellId": "1",
            "column": 1,
            "disabled": false,
            "hideCode": false,
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

      const { changes } = resolve(state, {
        type: "addColumnBreakpoint",
        payload: { cellId: b },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "cellId": "1",
            "column": 1,
            "disabled": false,
            "hideCode": false,
            "type": "set-config",
          },
          {
            "cellId": "2",
            "column": 1,
            "disabled": false,
            "hideCode": false,
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

      const { changes } = resolve(state, {
        type: "mergeAllColumns",
        payload: {},
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "cellId": "1",
            "column": 0,
            "disabled": false,
            "hideCode": false,
            "type": "set-config",
          },
          {
            "cellId": "2",
            "column": 0,
            "disabled": false,
            "hideCode": false,
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

  describe("cell lifecycle actions", () => {
    it("addColumn emits create-cell + column layout changes", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;
      const columnId = state.cellIds.findWithId(a).id;

      const { changes } = resolve(state, {
        type: "addColumn",
        payload: { columnId },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "after": "0",
            "cellId": "1",
            "code": "",
            "config": {
              "column": null,
              "disabled": false,
              "hide_code": false,
            },
            "name": "_",
            "type": "create-cell",
          },
          {
            "cellId": "1",
            "column": 1,
            "disabled": false,
            "hideCode": false,
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

    it("undoDeleteCell emits create-cell for restored cell", () => {
      setup("a", "b");
      const [, b] = state.cellIds.inOrderIds;

      // Delete cell b, then undo
      state = dispatch(state, {
        type: "deleteCell",
        payload: { cellId: b },
      });

      const { changes } = resolve(state, {
        type: "undoDeleteCell",
        payload: {},
      });

      // Restored cell should have original code
      expect(changes[0]).toMatchObject({
        type: "create-cell",
        code: "b",
      });
    });

    it("splitCell emits set-code + create-cell", () => {
      setup("line1\nline2");
      const [a] = state.cellIds.inOrderIds;

      // Position cursor at end of "line1" (position 5)
      const view = state.cellHandles[a].current!.editorView;
      view.dispatch({ selection: { anchor: 5 } });

      const { changes } = resolve(state, {
        type: "splitCell",
        payload: { cellId: a },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "cellId": "0",
            "code": "line1",
            "type": "set-code",
          },
          {
            "after": "0",
            "cellId": "1",
            "code": "line2",
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

    it("undoSplitCell emits set-code + delete-cell", () => {
      setup("line1\nline2");
      const [a] = state.cellIds.inOrderIds;

      // Split the cell first
      const view = state.cellHandles[a].current!.editorView;
      view.dispatch({ selection: { anchor: 5 } });
      const snapshot = view.state.doc.toString();
      state = dispatch(state, {
        type: "splitCell",
        payload: { cellId: a },
      });
      const [, newCell] = state.cellIds.inOrderIds;

      // Now undo the split
      const { changes } = resolve(state, {
        type: "undoSplitCell",
        payload: { cellId: a, snapshot },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "cellId": "0",
            "code": "line1
        line2",
            "type": "set-code",
          },
          {
            "cellId": "${newCell}",
            "type": "delete-cell",
          },
        ]
      `);
    });

    it("moveToNextCell emits create-cell when past last cell", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;

      const { changes } = resolve(state, {
        type: "moveToNextCell",
        payload: { cellId: a, before: false },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "after": "0",
            "cellId": "1",
            "code": "",
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

    it("moveToNextCell emits nothing when moving within bounds", () => {
      setup("a", "b");
      const [a] = state.cellIds.inOrderIds;

      const { changes } = resolve(state, {
        type: "moveToNextCell",
        payload: { cellId: a, before: false },
      });

      expect(changes).toHaveLength(0);
    });

    it("addSetupCellIfDoesntExist emits create-cell when new", () => {
      setup("a");

      const { changes } = resolve(state, {
        type: "addSetupCellIfDoesntExist",
        payload: { code: "import marimo as mo" },
      });

      expect(changes).toMatchInlineSnapshot(`
        [
          {
            "before": "0",
            "cellId": "setup",
            "code": "import marimo as mo",
            "config": {
              "column": null,
              "disabled": false,
              "hide_code": false,
            },
            "name": "setup",
            "type": "create-cell",
          },
        ]
      `);
    });

    it("addSetupCellIfDoesntExist emits nothing when already exists", () => {
      setup("a");
      // Add setup cell first
      state = dispatch(state, {
        type: "addSetupCellIfDoesntExist",
        payload: { code: "import marimo as mo" },
      });

      // Try to add again — should just focus
      const { changes } = resolve(state, {
        type: "addSetupCellIfDoesntExist",
        payload: {},
      });

      expect(changes).toHaveLength(0);
    });
  });

  describe("actions that should NOT emit changes", () => {
    it("focusCell returns empty", () => {
      setup("a", "b");
      const [a] = state.cellIds.inOrderIds;
      const { changes } = resolve(state, {
        type: "focusCell",
        payload: { cellId: a, where: "after" },
      });
      expect(changes).toHaveLength(0);
    });

    it("prepareForRun returns empty", () => {
      setup("a");
      const [a] = state.cellIds.inOrderIds;
      const { changes } = resolve(state, {
        type: "prepareForRun",
        payload: { cellId: a },
      });
      expect(changes).toHaveLength(0);
    });
  });
});
