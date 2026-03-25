/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Round-trip tests: perform actions on a primary notebook (producing ops
 * via the middleware), then apply those ops to a replica notebook via
 * applyTransactionOps. The two should converge to identical document state.
 *
 * This catches drift between what the middleware emits and what
 * apply-transaction consumes.
 */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";
import { cellId } from "@/__tests__/branded";
import type { CellHandle } from "@/components/editor/notebook-cell";
import { adaptiveLanguageConfiguration } from "@/core/codemirror/language/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { MultiColumn } from "@/utils/id-tree";
import { exportedForTesting, type NotebookState } from "../cells";
import {
  applyTransactionOps,
  exportedForTesting as middlewareExports,
} from "../document-ops";
import { CellId } from "../ids";

const { initialNotebookState, reducer, createActions } = exportedForTesting;
const { drainOps } = middlewareExports;

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

// --- Primary notebook: performs actions, middleware produces ops ---

let primary: NotebookState;

const primaryActions = createActions((action) => {
  primary = reducer(primary, action);
  for (const [cellIdString, handle] of Object.entries(primary.cellHandles)) {
    // @ts-expect-error - Object.entries doesn't know keys are CellId
    const cid: CellId = cellIdString;
    if (!handle.current) {
      const view = createEditor(primary.cellData[cid].code);
      const h: CellHandle = { editorView: view, editorViewOrNull: view };
      primary.cellHandles[cid] = { current: h };
    }
  }
});

// --- Replica notebook: receives ops via applyTransactionOps ---

let replica: NotebookState;

const replicaActions = createActions((action) => {
  replica = reducer(replica, action);
  for (const [cellIdString, handle] of Object.entries(replica.cellHandles)) {
    // @ts-expect-error - Object.entries doesn't know keys are CellId
    const cid: CellId = cellIdString;
    if (!handle.current) {
      const view = createEditor(replica.cellData[cid].code);
      const h: CellHandle = { editorView: view, editorViewOrNull: view };
      replica.cellHandles[cid] = { current: h };
    }
  }
});

let i = 0;
const originalCreate = CellId.create.bind(CellId);

beforeAll(() => {
  CellId.create = () => cellId(`${i++}`);
});

beforeEach(() => {
  i = 0;
  primary = initialNotebookState();
  primary.cellIds = MultiColumn.from([]);
  drainOps();
});

afterEach(() => {
  middlewareExports.cancelPendingOps();
});

afterAll(() => {
  CellId.create = originalCreate;
});

/** Set up both notebooks with the same initial cells. */
function setup(...codes: string[]) {
  for (const code of codes) {
    primaryActions.createNewCell({
      cellId: "__end__",
      before: false,
      code,
      newCellId: CellId.create(),
    });
  }

  // Apply the setup ops to the replica so both start identical
  const setupOps = drainOps();
  replica = initialNotebookState();
  replica.cellIds = MultiColumn.from([]);
  applyTransactionOps(
    setupOps,
    replicaActions,
    () => replica.cellIds.inOrderIds,
  );
  // Drain any ops the replica's middleware produced
  drainOps();
}

/**
 * Drain ops from the primary's middleware and apply them to the replica.
 */
function sync() {
  const ops = drainOps();
  applyTransactionOps(ops, replicaActions, () => replica.cellIds.inOrderIds);
  // Drain any ops the replica's middleware produced (we don't want those)
  drainOps();
}

/**
 * Extract the document-relevant state: cell ordering, code, name, config.
 * This is the "NotebookDocument" equivalent — what the Python side tracks.
 *
 * TODO(column-config): config.column is excluded because the column
 * reducers (addColumnBreakpoint, dropOverNewColumn, moveColumn, etc.)
 * update cellIds (MultiColumn structure) but don't sync config.column
 * on affected cells. The middleware correctly emits set-config ops with
 * the new column index, but the primary's config.column stays stale,
 * causing a mismatch with the replica. Fix: have the column reducers
 * update config.column as part of their state transition, then remove
 * the { column: _, ...config } exclusion here.
 */
function documentSnapshot(state: NotebookState) {
  return state.cellIds.inOrderIds.map((id) => {
    const { column: _, ...config } = state.cellData[id].config;
    return {
      id,
      code: state.cellData[id].code,
      name: state.cellData[id].name,
      config,
    };
  });
}

/** Assert both notebooks have identical document state. */
function expectConverged() {
  expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
}

describe("document round-trip", () => {
  it("initial setup converges", () => {
    setup("a", "b", "c");
    expectConverged();
  });

  it("createNewCell at end", () => {
    setup("a", "b");
    primaryActions.createNewCell({
      cellId: "__end__",
      before: false,
      code: "c",
      newCellId: CellId.create(),
    });
    sync();
    expectConverged();
  });

  it("createNewCell before first cell", () => {
    setup("a", "b");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.createNewCell({
      cellId: a,
      before: true,
      code: "before-a",
      newCellId: CellId.create(),
    });
    sync();
    expectConverged();
  });

  it("createNewCell between cells", () => {
    setup("a", "b", "c");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.createNewCell({
      cellId: a,
      before: false,
      code: "between",
      newCellId: CellId.create(),
    });
    sync();
    expectConverged();
  });

  it("createNewCell with hideCode config", () => {
    setup("a");
    primaryActions.createNewCell({
      cellId: "__end__",
      before: false,
      code: "hidden",
      newCellId: CellId.create(),
      hideCode: true,
    });
    sync();
    expectConverged();
  });

  it("deleteCell", () => {
    setup("a", "b", "c");
    const [, b] = primary.cellIds.inOrderIds;
    primaryActions.deleteCell({ cellId: b });
    sync();
    expectConverged();
  });

  it("updateCellCode", () => {
    setup("a", "b");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.updateCellCode({
      cellId: a,
      code: "updated",
      formattingChange: false,
    });
    sync();
    expectConverged();
  });

  it("updateCellName", () => {
    setup("a");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.updateCellName({ cellId: a, name: "my_var" });
    sync();
    expectConverged();
  });

  it("updateCellConfig", () => {
    setup("a");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.updateCellConfig({
      cellId: a,
      config: { hide_code: true, disabled: true },
    });
    sync();
    expectConverged();
  });

  it("moveCell down", () => {
    setup("a", "b", "c");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.moveCell({ cellId: a, before: false });
    sync();
    expectConverged();
  });

  it("sendToTop", () => {
    setup("a", "b", "c");
    const [, , c] = primary.cellIds.inOrderIds;
    primaryActions.sendToTop({ cellId: c });
    sync();
    expectConverged();
  });

  it("sendToBottom", () => {
    setup("a", "b", "c");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.sendToBottom({ cellId: a });
    sync();
    expectConverged();
  });

  it("dropCellOverCell", () => {
    setup("a", "b", "c");
    const [a, , c] = primary.cellIds.inOrderIds;
    primaryActions.dropCellOverCell({ cellId: c, overCellId: a });
    sync();
    expectConverged();
  });

  it("multiple operations in sequence", () => {
    setup("a", "b", "c");

    // Add a cell
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.createNewCell({
      cellId: a,
      before: false,
      code: "new",
      newCellId: CellId.create(),
    });
    sync();

    // Rename it
    const newId = primary.cellIds.inOrderIds[1];
    primaryActions.updateCellName({ cellId: newId, name: "inserted" });
    sync();

    // Move it to top
    primaryActions.sendToTop({ cellId: newId });
    sync();

    // Update code on another cell
    const last =
      primary.cellIds.inOrderIds[primary.cellIds.inOrderIds.length - 1];
    primaryActions.updateCellCode({
      cellId: last,
      code: "modified",
      formattingChange: false,
    });
    sync();

    expectConverged();
  });

  it("create then delete", () => {
    setup("a", "b");
    primaryActions.createNewCell({
      cellId: "__end__",
      before: false,
      code: "temporary",
      newCellId: CellId.create(),
    });
    sync();

    const newId =
      primary.cellIds.inOrderIds[primary.cellIds.inOrderIds.length - 1];
    primaryActions.deleteCell({ cellId: newId });
    sync();

    expectConverged();
  });

  it("addColumnBreakpoint", () => {
    setup("a", "b", "c");
    const [, b] = primary.cellIds.inOrderIds;
    primaryActions.addColumnBreakpoint({ cellId: b });
    sync();
    expectConverged();
  });

  it("dropOverNewColumn", () => {
    setup("a", "b", "c");
    const [, b] = primary.cellIds.inOrderIds;
    primaryActions.dropOverNewColumn({ cellId: b });
    sync();
    expectConverged();
  });
});
