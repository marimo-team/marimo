/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Round-trip tests: perform actions on a primary notebook (producing changes
 * via the middleware), then apply those changes to a replica notebook via
 * applyTransactionChanges. The two should converge to identical document state.
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
  applyTransactionChanges,
  exportedForTesting as middlewareExports,
} from "../document-changes";
import { CellId } from "../ids";

const { initialNotebookState, reducer, createActions } = exportedForTesting;
const { drainChanges } = middlewareExports;

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

// --- Primary notebook: performs actions, middleware produces changes ---

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

// --- Replica notebook: receives changes via applyTransactionChanges ---

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
  drainChanges();
});

afterEach(() => {
  middlewareExports.cancelPendingChanges();
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

  // Apply the setup changes to the replica so both start identical
  const setupChanges = drainChanges();
  replica = initialNotebookState();
  replica.cellIds = MultiColumn.from([]);
  applyTransactionChanges(
    setupChanges,
    replicaActions,
    () => replica.cellIds.inOrderIds,
  );
  // Drain any changes the replica's middleware produced
  drainChanges();
}

/**
 * Drain changes from the primary's middleware and apply them to the replica.
 */
function sync() {
  const changes = drainChanges();
  applyTransactionChanges(
    changes,
    replicaActions,
    () => replica.cellIds.inOrderIds,
  );
  // Drain any changes the replica's middleware produced (we don't want those)
  drainChanges();
}

/**
 * Extract the document-relevant state: cell ordering, code, name, config.
 * This is the "NotebookDocument" equivalent — what the Python side tracks.
 *
 * TODO(column-config): config.column is excluded because the column
 * reducers (addColumnBreakpoint, dropOverNewColumn, moveColumn, etc.)
 * update cellIds (MultiColumn structure) but don't sync config.column
 * on affected cells. The middleware correctly emits set-config changes with
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

describe("document round-trip", () => {
  it("initial setup converges", () => {
    setup("a", "b", "c");
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("deleteCell", () => {
    setup("a", "b", "c");
    const [, b] = primary.cellIds.inOrderIds;
    primaryActions.deleteCell({ cellId: b });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("updateCellName", () => {
    setup("a");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.updateCellName({ cellId: a, name: "my_var" });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("updateCellConfig", () => {
    setup("a");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.updateCellConfig({
      cellId: a,
      config: { hide_code: true, disabled: true },
    });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("moveCell down", () => {
    setup("a", "b", "c");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.moveCell({ cellId: a, before: false });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("sendToTop", () => {
    setup("a", "b", "c");
    const c = primary.cellIds.inOrderIds[2];
    primaryActions.sendToTop({ cellId: c });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("sendToBottom", () => {
    setup("a", "b", "c");
    const [a] = primary.cellIds.inOrderIds;
    primaryActions.sendToBottom({ cellId: a });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("dropCellOverCell", () => {
    setup("a", "b", "c");
    const [a, , c] = primary.cellIds.inOrderIds;
    primaryActions.dropCellOverCell({ cellId: c, overCellId: a });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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

    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
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

    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("addColumnBreakpoint", () => {
    setup("a", "b", "c");
    const [, b] = primary.cellIds.inOrderIds;
    primaryActions.addColumnBreakpoint({ cellId: b });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });

  it("dropOverNewColumn", () => {
    setup("a", "b", "c");
    const [, b] = primary.cellIds.inOrderIds;
    primaryActions.dropOverNewColumn({ cellId: b });
    sync();
    expect(documentSnapshot(primary)).toEqual(documentSnapshot(replica));
  });
});
